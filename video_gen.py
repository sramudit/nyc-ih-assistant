import asyncio
import base64
import io
import os
import tempfile
import textwrap
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple
import edge_tts
from dotenv import load_dotenv
from google import genai
from google.genai import types
from moviepy import AudioFileClip, ImageClip, VideoFileClip, concatenate_videoclips, vfx
from PIL import Image, ImageDraw, ImageFont

load_dotenv()


def _get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY in .env file.")
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version="v1beta", timeout=180_000),
    )


def _get_font(size: int, bold: bool = False):
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
    ]
    for path in candidates:
        if Path(path).exists():
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def render_slide_card_png(scene: Dict) -> bytes:
    """Create a 1280x720 civic-navy reference slide card for Gemini Omni 1.2 Flash."""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, W, 14], fill=(37, 99, 235))
    draw.rounded_rectangle([64, 70, W - 64, H - 70], radius=24, fill=(248, 250, 252))

    font_badge = _get_font(24, bold=True)
    font_title = _get_font(46, bold=True)
    font_body = _get_font(34, bold=False)
    font_cite = _get_font(22, bold=False)

    scene_num = scene.get("scene_number", 1)
    badge_txt = f"PARENT BRIEFING • SCENE {scene_num}"
    bbox = draw.textbbox((0, 0), badge_txt, font=font_badge)
    box_w = (bbox[2] - bbox[0]) + 44
    draw.rounded_rectangle([110, 110, 110 + box_w, 158], radius=12, fill=(30, 64, 175))
    draw.text((132, 120), badge_txt, fill=(255, 255, 255), font=font_badge)

    title_lines = textwrap.wrap(scene.get("slide_title", "Key Hearing Lesson"), width=34)
    y = 190
    for line in title_lines[:2]:
        draw.text((110, y), line, fill=(15, 23, 42), font=font_title)
        y += 58

    draw.line([110, y + 12, W - 110, y + 12], fill=(203, 213, 225), width=3)

    takeaway_lines = textwrap.wrap(scene.get("key_takeaway", ""), width=48)
    y += 45
    for line in takeaway_lines[:5]:
        draw.text((110, y), line, fill=(51, 65, 85), font=font_body)
        y += 48

    cite = scene.get("evidence_citation", "Record Citation")
    draw.text((110, H - 130), f"Source: {cite}", fill=(100, 116, 139), font=font_cite)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def render_detailed_slide_png(
    segment_num: int,
    segment_title: str,
    slide: Dict[str, Any],
    slide_idx: int,
    total_slides: int,
    active_bullet_idx: int = 99,
) -> bytes:
    """Render a 1280x720 progressive-reveal slide frame with active bullet highlight & progress bar."""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), color=(15, 23, 42))
    draw = ImageDraw.Draw(img)

    # Top segment progress bar
    bullets = slide.get("bullets", [])[:3] or [slide.get("slide_title", "Key Point")]
    total_steps = max(len(bullets), 1)
    step_progress = min(active_bullet_idx + 1, total_steps) / total_steps
    overall_pct = ((slide_idx - 1) + step_progress) / max(total_slides, 1)
    draw.rectangle([0, 0, W, 14], fill=(30, 41, 59))
    draw.rectangle([0, 0, int(W * overall_pct), 14], fill=(59, 130, 246))

    draw.rounded_rectangle([54, 56, W - 54, H - 56], radius=22, fill=(248, 250, 252))

    font_badge = _get_font(22, bold=True)
    font_title = _get_font(40, bold=True)
    font_bullet = _get_font(28, bold=False)
    font_bullet_bold = _get_font(28, bold=True)
    font_cite = _get_font(21, bold=False)

    badge_text = f"PART {segment_num} OF 3: {segment_title.upper()} ({slide_idx}/{total_slides})"[:64]
    bbox = draw.textbbox((0, 0), badge_text, font=font_badge)
    box_w = min((bbox[2] - bbox[0]) + 44, W - 192)
    draw.rounded_rectangle([96, 88, 96 + box_w, 132], radius=10, fill=(30, 64, 175))
    draw.text((118, 98), badge_text, fill=(255, 255, 255), font=font_badge)

    y = 152
    for line in textwrap.wrap(slide.get("slide_title", ""), width=40)[:2]:
        draw.text((96, y), line, fill=(15, 23, 42), font=font_title)
        y += 48

    draw.line([96, y + 8, W - 96, y + 8], fill=(203, 213, 225), width=3)
    y += 30

    for b_num, bullet in enumerate(bullets):
        if b_num > active_bullet_idx:
            continue  # Progressive reveal: upcoming bullets fade in on next beat

        is_active = (b_num == active_bullet_idx)
        wrapped = textwrap.wrap(bullet, width=55)[:3]
        block_h = len(wrapped) * 37 + 12

        if is_active:
            draw.rounded_rectangle([90, y - 6, W - 90, y + block_h - 4], radius=10, fill=(239, 246, 255))
            draw.rectangle([90, y - 6, 98, y + block_h - 4], fill=(37, 99, 235))

        txt_color = (30, 58, 138) if is_active else (51, 65, 85)
        use_font = font_bullet_bold if is_active else font_bullet
        for b_idx, b_line in enumerate(wrapped):
            prefix = "▸  " if (b_idx == 0 and is_active) else ("•  " if b_idx == 0 else "   ")
            draw.text((112, y), f"{prefix}{b_line}", fill=txt_color, font=use_font)
            y += 37
        y += 18

    if active_bullet_idx >= len(bullets) - 1:
        cite = slide.get("citation", "Record Citation")
        draw.text((96, H - 108), f"Source Citation: {cite}", fill=(30, 64, 175), font=font_cite)

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def build_full_3min_guide(
    guide_script: Dict[str, Any],
    include_omni_intro: bool = True,
    omni_resolution: str = "360p",
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[bytes, List[Tuple[str, bytes]]]:
    """
    Build 3 progressive-animated ~1-minute segments + optional Omni 1.2 Flash animated intro,
    and stitch into one downloadable ~3-minute MP4.
    """
    out_dir = Path("generated_videos")
    out_dir.mkdir(exist_ok=True)
    segment_outputs: List[Tuple[str, bytes]] = []
    part_paths: List[Path] = []

    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp)

        if include_omni_intro and guide_script.get("intro_hook"):
            if progress_cb:
                progress_cb("Generating animated opener with Gemini Omni 1.2 Flash (~12s)...")
            intro_scene = dict(guide_script["intro_hook"])
            intro_scene["scene_number"] = 0
            try:
                intro_bytes, _, _ = generate_teaching_clip(
                    intro_scene, resolution=omni_resolution, duration_seconds=12
                )
                intro_path = tmp_dir / "00_omni_intro.mp4"
                intro_path.write_bytes(intro_bytes)
                part_paths.append(intro_path)
            except Exception as exc:
                if progress_cb:
                    progress_cb(f"Omni intro skipped ({exc}); continuing with 3 narrated segments...")

        segments = guide_script.get("segments", [])
        for seg in segments:
            seg_num = seg.get("segment_number", 1)
            seg_title = seg.get("segment_title", f"Segment {seg_num}")
            slides = seg.get("slides", [])
            if progress_cb:
                progress_cb(f"Rendering animated Segment {seg_num}/3: {seg_title} (~1 min)...")

            slide_clips = []
            all_temp_clips = []
            open_audio = []
            try:
                for idx, slide in enumerate(slides, start=1):
                    mp3_path = tmp_dir / f"seg{seg_num}_slide{idx}.mp3"
                    narration_txt = slide.get("narration", "") or "Review this key finding."
                    _run_async(_tts_to_file(narration_txt, mp3_path))

                    a_clip = AudioFileClip(str(mp3_path))
                    open_audio.append(a_clip)

                    bullets = slide.get("bullets", [])[:3] or [slide.get("slide_title", "Key Point")]
                    n_beats = len(bullets)
                    beat_dur = (a_clip.duration + 0.4) / n_beats

                    beat_clips = []
                    for beat_idx in range(n_beats):
                        png_bytes = render_detailed_slide_png(
                            seg_num, seg_title, slide, idx, len(slides), active_bullet_idx=beat_idx
                        )
                        png_path = tmp_dir / f"seg{seg_num}_slide{idx}_b{beat_idx}.png"
                        png_path.write_bytes(png_bytes)

                        b_clip = ImageClip(str(png_path)).with_duration(beat_dur)
                        if beat_idx == 0:
                            b_clip = b_clip.with_effects([vfx.FadeIn(0.25)])
                        beat_clips.append(b_clip)
                        all_temp_clips.append(b_clip)

                    slide_seq = concatenate_videoclips(beat_clips, method="chain").with_audio(a_clip)
                    slide_clips.append(slide_seq)
                    all_temp_clips.append(slide_seq)

                seg_video = concatenate_videoclips(slide_clips, method="compose")
                seg_mp4_path = out_dir / f"segment_{seg_num}.mp4"
                seg_video.write_videofile(
                    str(seg_mp4_path),
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    logger=None,
                )
                seg_video.close()
                part_paths.append(seg_mp4_path)
                segment_outputs.append((f"Segment {seg_num}: {seg_title}", seg_mp4_path.read_bytes()))
            finally:
                for c in all_temp_clips:
                    c.close()
                for a in open_audio:
                    a.close()

        if progress_cb:
            progress_cb("Stitching Omni intro + all 3 animated segments into your 3-minute MP4...")

        loaded_clips = []
        try:
            for p in part_paths:
                vc = VideoFileClip(str(p)).resized((1280, 720))
                loaded_clips.append(vc)

            final_video = concatenate_videoclips(loaded_clips, method="compose")
            final_path = out_dir / "full_3min_parent_guide.mp4"
            final_video.write_videofile(
                str(final_path),
                fps=24,
                codec="libx264",
                audio_codec="aac",
                logger=None,
            )
            final_video.close()
            return final_path.read_bytes(), segment_outputs
        finally:
            for vc in loaded_clips:
                vc.close()


def _extract_video_bytes(interaction) -> Optional[bytes]:
    out_vid = getattr(interaction, "output_video", None)
    if out_vid is not None and getattr(out_vid, "data", None):
        data = out_vid.data
        return base64.b64decode(data) if isinstance(data, str) else data

    for out in getattr(interaction, "outputs", None) or []:
        if getattr(out, "type", "") == "video":
            data = getattr(out, "data", None) or getattr(out, "video_bytes", None)
            if data:
                return base64.b64decode(data) if isinstance(data, str) else data
    return None


def generate_teaching_clip(
    scene: Dict,
    resolution: str = "360p",
    duration_seconds: int = 12,
    previous_interaction_id: Optional[str] = None,
) -> Tuple[bytes, str, bytes]:
    """Generate a crisp 10-15s motion clip using Gemini Omni 1.2 Flash."""
    client = _get_client()
    slide_png = render_slide_card_png(scene)
    slide_b64 = base64.b64encode(slide_png).decode("utf-8")

    narration = scene.get("narration_script", "")
    visual_cue = scene.get("visual_prompt", "Clean editorial educational animation")
    prompt = (
        f"Create a {duration_seconds}-second calm educational explainer video based on the provided reference slide. "
        f"Keep the layout clean, legible, and professional. Visual style: {visual_cue}. "
        f"Complete the entire spoken voiceover calmly before the {duration_seconds}-second clip ends, saying: \"{narration}\""
    )

    out_dir = Path("generated_videos")
    out_dir.mkdir(exist_ok=True)

    kwargs = {
        "model": "gemini-omni-1.2-flash",
        "input": [
            {"type": "text", "text": prompt},
            {"type": "image", "data": slide_b64, "mime_type": "image/png"},
        ],
        "response_modalities": ["video"],
        "generation_config": {
            "video_config": {
                "aspect_ratio": "16:9",
                "resolution": resolution,
                "duration_seconds": duration_seconds,
            }
        },
    }
    if previous_interaction_id:
        kwargs["previous_interaction_id"] = previous_interaction_id

    try:
        interaction = client.interactions.create(**kwargs)
    except Exception:
        interaction = client.interactions.create(
            model="gemini-omni-1.2-flash",
            input=prompt,
        )

    video_bytes = _extract_video_bytes(interaction)
    if not video_bytes:
        raise RuntimeError("Omni 1.2 Flash returned no video payload.")

    scene_num = scene.get("scene_number", 1)
    out_path = out_dir / f"omni_clip_{scene_num}_{resolution}.mp4"
    out_path.write_bytes(video_bytes)
    return video_bytes, getattr(interaction, "id", ""), slide_png


def _run_async(coro):
    try:
        return asyncio.run(coro)
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


async def _tts_to_file(text: str, out_path: Path, voice: str = "en-US-AriaNeural"):
    comm = edge_tts.Communicate(text, voice)
    await comm.save(str(out_path))



def verify_video_with_gemini4(video_bytes: bytes, expected_summary: str) -> str:
    """Use Gemini 4 Hydrogen video understanding to verify the generated video."""
    client = _get_client()
    b64_vid = base64.b64encode(video_bytes).decode("utf-8")
    prompt = (
        f"Watch this parent-training video and confirm in 3 crisp bullet points: "
        f"(1) Is on-screen text legible? "
        f"(2) Is the spoken narration complete without cutting off? "
        f"(3) Does it align accurately with these case findings: {expected_summary[:1200]}?"
    )
    interaction = client.interactions.create(
        model="gemini-4-hydrogen",
        input=[
            {"type": "text", "text": prompt},
            {"type": "video", "data": b64_vid, "mime_type": "video/mp4"},
        ],
    )
    return interaction.output_text

def build_stitched_omni_video(
    beats: List[Dict[str, Any]],
    resolution: str = "360p",
    duration_seconds: int = 14,
    progress_cb: Optional[Callable[[str], None]] = None,
) -> Tuple[bytes, List[bytes]]:
    """Generate multiple 14s Gemini Omni 1.2 Flash clips guided by matching Pillow cards and stitch into one MP4."""
    out_dir = Path("generated_videos")
    out_dir.mkdir(exist_ok=True)
    clip_paths: List[Path] = []
    clip_bytes_list: List[bytes] = []

    for idx, beat in enumerate(beats, start=1):
        beat["scene_number"] = idx
        if progress_cb:
            progress_cb(
                f"Generating Omni 1.2 Flash clip {idx}/{len(beats)}: {beat.get('slide_title', '')}..."
            )
        vid_bytes, _, _ = generate_teaching_clip(
            beat, resolution=resolution, duration_seconds=duration_seconds
        )
        p = out_dir / f"omni_stitch_{idx}_{resolution}.mp4"
        p.write_bytes(vid_bytes)
        clip_paths.append(p)
        clip_bytes_list.append(vid_bytes)

    if progress_cb:
        progress_cb(f"Stitching {len(clip_paths)} Omni 1.2 Flash clips into one video...")

    loaded = []
    try:
        for p in clip_paths:
            loaded.append(VideoFileClip(str(p)).resized((1280, 720)))
        final_vid = concatenate_videoclips(loaded, method="compose")
        final_path = out_dir / f"full_omni_stitched_{len(clip_paths)}x{duration_seconds}s.mp4"
        final_vid.write_videofile(
            str(final_path),
            fps=24,
            codec="libx264",
            audio_codec="aac",
            logger=None,
        )
        final_vid.close()
        return final_path.read_bytes(), clip_bytes_list
    finally:
        for vc in loaded:
            vc.close()