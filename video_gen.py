import base64
import io
import os
import textwrap
from pathlib import Path
from typing import Dict, Optional, Tuple
from dotenv import load_dotenv
from google import genai
from google.genai import types
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


def render_slide_card_png(scene: Dict) -> bytes:
    """Create a crisp 1280x720 civic-navy reference slide card for Gemini Omni 1.2 Flash."""
    W, H = 1280, 720
    img = Image.new("RGB", (W, H), color=(15, 23, 42))  # Deep slate navy
    draw = ImageDraw.Draw(img)

    # Top accent bar & card panel
    draw.rectangle([0, 0, W, 14], fill=(37, 99, 235))
    draw.rounded_rectangle([64, 70, W - 64, H - 70], radius=24, fill=(248, 250, 252))

    # Load clean default or system Arial font on Windows/Mac
    def get_font(size: int, bold: bool = False):
        candidates = [
            "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
            "/System/Library/Fonts/Supplemental/Arial Bold.ttf" if bold else "/System/Library/Fonts/Supplemental/Arial.ttf",
        ]
        for path in candidates:
            if Path(path).exists():
                return ImageFont.truetype(path, size)
        return ImageFont.load_default()

    font_badge = get_font(24, bold=True)
    font_title = get_font(46, bold=True)
    font_body = get_font(34, bold=False)
    font_cite = get_font(22, bold=False)

    scene_num = scene.get("scene_number", 1)
    draw.rounded_rectangle([110, 110, 410, 158], radius=12, fill=(30, 64, 175))
    draw.text((132, 120), f"IHO INSIGHT • SCENE {scene_num}", fill=(255, 255, 255), font=font_badge)

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


def _extract_video_bytes(interaction) -> Optional[bytes]:
    """Handle both interaction.output_video.data and interaction.outputs video payloads."""
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
    duration_seconds: int = 8,
    previous_interaction_id: Optional[str] = None,
) -> Tuple[bytes, str, bytes]:
    """
    Generate a narrated parent-academy clip using Gemini Omni 1.2 Flash.
    Returns: (mp4_bytes, interaction_id, reference_slide_png_bytes)
    """
    client = _get_client()
    slide_png = render_slide_card_png(scene)
    slide_b64 = base64.b64encode(slide_png).decode("utf-8")

    narration = scene.get("narration_script", "")
    visual_cue = scene.get("visual_prompt", "Clean editorial educational animation")
    prompt = (
        f"Create a clear, calm educational explainer video based on the provided reference slide. "
        f"Keep the layout clean, legible, and professional. Visual style: {visual_cue}. "
        f"Include clear, warm spoken voiceover narration saying exactly: \"{narration}\""
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
        # Clean fallback to simple text-prompt schema if endpoint rejects multimodal/video_config keys
        interaction = client.interactions.create(
            model="gemini-omni-1.2-flash",
            input=prompt,
        )

    video_bytes = _extract_video_bytes(interaction)
    if not video_bytes:
        raise RuntimeError(
            f"Omni 1.2 Flash returned no video payload (status={getattr(interaction, 'status', 'unknown')})."
        )

    scene_num = scene.get("scene_number", 1)
    out_path = out_dir / f"iho_lesson_scene_{scene_num}_{resolution}.mp4"
    out_path.write_bytes(video_bytes)

    return video_bytes, getattr(interaction, "id", ""), slide_png


def verify_video_with_gemini4(video_bytes: bytes, expected_summary: str) -> str:
    """Use Gemini 4 Hydrogen video understanding to sanity-check the generated clip."""
    client = _get_client()
    b64_vid = base64.b64encode(video_bytes).decode("utf-8")
    prompt = (
        f"Watch this short parent-training clip and confirm in 2-3 bullet points: "
        f"(1) Is any on-screen text legible? "
        f"(2) Does the spoken narration accurately align with this ruling summary: {expected_summary}?"
    )
    interaction = client.interactions.create(
        model="gemini-4-hydrogen",
        input=[
            {"type": "text", "text": prompt},
            {"type": "video", "data": b64_vid, "mime_type": "video/mp4"},
        ],
    )
    return interaction.output_text