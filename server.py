import os
import sys
import re
import json
import uuid
import shutil
import zipfile
import asyncio
import webbrowser
import subprocess
from pathlib import Path
from typing import List, Optional, Dict, Any

import httpx
import edge_tts
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from PIL import Image, ImageDraw, ImageFont, ImageFilter

# Ensure common macOS/Homebrew, Windows, and bundled bin directories are on PATH for ffmpeg/ffprobe
if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
    BUNDLE_DIR = Path(sys._MEIPASS)
    EXE_DIR = Path(sys.executable).resolve().parent
    WORK_DIR = Path.home() / "Library" / "Application Support" / "SubcastStudio"
    extra_paths = [str(EXE_DIR), str(BUNDLE_DIR), os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin"]
    os.environ["PATH"] = os.pathsep.join([p for p in extra_paths if p])
else:
    BUNDLE_DIR = Path(__file__).resolve().parent
    WORK_DIR = BUNDLE_DIR
    extra_paths = [str(BUNDLE_DIR), os.environ.get("PATH", ""), "/opt/homebrew/bin", "/usr/local/bin"]
    os.environ["PATH"] = os.pathsep.join([p for p in extra_paths if p])

BASE_DIR = WORK_DIR
STATIC_DIR = BUNDLE_DIR / "static"
UPLOADS_DIR = WORK_DIR / "uploads"
OUTPUTS_DIR = WORK_DIR / "outputs"
FONTS_DIR = WORK_DIR / "fonts"
MODELS_DIR = WORK_DIR / "models"

for d in [UPLOADS_DIR, OUTPUTS_DIR, FONTS_DIR, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

app = FastAPI(title="Subtitle & Typecast Overlay Studio")

# System default Korean fonts on macOS & Windows
DEFAULT_FONTS = [
    {"id": "system-apple-sd", "name": "Apple SD 산돌고딕 Neo (System)", "path": "/System/Library/Fonts/AppleSDGothicNeo.ttc"},
    {"id": "system-apple-gothic", "name": "AppleGothic (System)", "path": "/System/Library/Fonts/Supplemental/AppleGothic.ttf"},
    {"id": "system-arial-uni", "name": "Arial Unicode MS (System)", "path": "/Library/Fonts/Arial Unicode.ttf"},
    {"id": "system-malgun-bold", "name": "맑은 고딕 Bold (System)", "path": "C:/Windows/Fonts/malgunbd.ttf"},
    {"id": "system-malgun", "name": "맑은 고딕 (System)", "path": "C:/Windows/Fonts/malgun.ttf"},
]


def hex_to_rgba(hex_str: str, opacity: float = 1.0) -> tuple:
    hex_str = hex_str.lstrip("#")
    if len(hex_str) == 3:
        hex_str = "".join([c * 2 for c in hex_str])
    if len(hex_str) != 6:
        return (255, 255, 255, int(opacity * 255))
    r = int(hex_str[0:2], 16)
    g = int(hex_str[2:4], 16)
    b = int(hex_str[4:6], 16)
    a = int(max(0.0, min(1.0, opacity)) * 255)
    return (r, g, b, a)


def sanitize_spoken_text(
    text: str,
    exclude_numbers: bool = False,
    exclude_special: bool = False,
    custom_exclude_chars: str = "",
) -> str:
    """
    Removes numbers and/or special characters for the TTS spoken prompt
    while keeping spaces and Hangul/Latin letters intact.
    """
    result = text
    if custom_exclude_chars:
        for ch in custom_exclude_chars:
            result = result.replace(ch, " ")
    if exclude_numbers:
        result = re.sub(r"[0-9]+", " ", result)
    if exclude_special:
        # Keep Korean syllables/jamo, English letters, numbers (if not excluded), and basic whitespace
        result = re.sub(r"[^가-힣ㄱ-ㅎㅏ-ㅣa-zA-Z0-9\s]", " ", result)
    # Collapse repeated spaces
    result = re.sub(r"\s+", " ", result).strip()
    return result


def get_audio_duration(audio_path: Path) -> float:
    """Get exact duration of an audio file using ffprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(audio_path),
        ]
        out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8").strip()
        return max(0.2, float(out))
    except Exception:
        return 2.0


def generate_fallback_wav(output_path: Path, duration: float = 2.0):
    """Generates a clean silent WAV file if offline or TTS fails."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "anullsrc=r=44100:cl=mono",
        "-t", str(duration),
        "-q:a", "9",
        "-acodec", "pcm_s16le",
        str(output_path),
    ]
    subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


_typecast_voice_models: Dict[str, List[str]] = {}


def _map_typecast_emotion_preset(emotion: str) -> str:
    if not emotion:
        return "normal"
    clean = emotion.strip().lower()
    mapping = {
        "normal-1": "normal",
        "happy-1": "happy",
        "sad-1": "sad",
        "angry-1": "angry",
        "tonemid-1": "tonedown",
    }
    if clean in mapping:
        return mapping[clean]
    return clean.split("-")[0] if "-" in clean else clean


async def synthesize_typecast(
    text: str,
    api_key: str,
    actor_id: str,
    speed: float,
    pitch: int,
    emotion: str,
    output_path: Path,
) -> dict:
    """
    Calls Typecast API to synthesize speech and downloads the resulting audio.
    Supports official Typecast API (`https://api.typecast.ai/v1/text-to-speech`)
    as well as legacy Typecast speak endpoints.
    """
    clean_key = api_key.strip()
    clean_actor = actor_id.strip()
    emotion_preset = _map_typecast_emotion_preset(emotion)

    candidate_models = list(_typecast_voice_models.get(clean_actor, []))
    for fallback_m in ("ssfm-v31", "ssfm-v30", "ssfm-v21"):
        if fallback_m not in candidate_models:
            candidate_models.append(fallback_m)

    last_err_detail = ""
    async with httpx.AsyncClient(timeout=60.0) as client:
        # 1. Try official Typecast API (https://api.typecast.ai/v1/text-to-speech)
        tts_headers = {
            "X-API-KEY": clean_key,
            "Content-Type": "application/json",
        }
        for model_ver in candidate_models:
            v1_payload = {
                "voice_id": clean_actor,
                "text": text,
                "model": model_ver,
                "prompt": {
                    "emotion_type": "preset",
                    "emotion_preset": emotion_preset,
                },
                "output": {
                    "volume": 100,
                    "audio_pitch": int(pitch),
                    "audio_tempo": float(speed),
                    "audio_format": "wav",
                },
            }
            try:
                resp = await client.post(
                    "https://api.typecast.ai/v1/text-to-speech",
                    headers=tts_headers,
                    json=v1_payload,
                )
                if resp.status_code == 200 and resp.content:
                    output_path.write_bytes(resp.content)
                    return {"engine": "typecast", "path": str(output_path)}
                last_err_detail = f"HTTP {resp.status_code}: {resp.text[:300]}"
                # If unauthorized, no need to retry other ssfm models on the same endpoint
                if resp.status_code in (401, 403):
                    break
            except Exception as e:
                last_err_detail = str(e)

        # 2. Fallback to legacy Typecast v1/speak endpoint
        legacy_headers = {
            "Authorization": f"Bearer {clean_key}",
            "X-API-KEY": clean_key,
            "Content-Type": "application/json",
        }
        legacy_payload = {
            "text": text,
            "actor_id": clean_actor,
            "lang": "auto",
            "xapi_hd": True,
            "model_version": "latest",
            "tempo": speed,
            "pitch": pitch,
            "emotion_tone_preset": emotion or "normal-1",
        }
        resp = await client.post("https://typecast.ai/api/speak", headers=legacy_headers, json=legacy_payload)
        if resp.status_code not in (200, 201, 202):
            detail_msg = last_err_detail or f"HTTP {resp.status_code}: {resp.text[:300]}"
            raise HTTPException(
                status_code=400,
                detail=f"Typecast API 호출 실패 ({detail_msg})",
            )

        data = resp.json()
        result_obj = data.get("result", data) if isinstance(data, dict) else {}

        speak_url = result_obj.get("speak_v2_url") or result_obj.get("speak_url") or result_obj.get("url")
        audio_download_url = result_obj.get("audio_download_url") or result_obj.get("audio_url")

        if not audio_download_url and speak_url:
            for _ in range(45):
                await asyncio.sleep(1.0)
                poll = await client.get(speak_url, headers=legacy_headers)
                if poll.status_code == 200:
                    p_json = poll.json()
                    p_data = p_json.get("result", p_json) if isinstance(p_json, dict) else {}
                    status = p_data.get("status")
                    if status == "done":
                        audio_download_url = p_data.get("audio_download_url") or p_data.get("audio_url")
                        break
                    elif status in ("failed", "error"):
                        raise HTTPException(status_code=400, detail=f"Typecast 음성 합성 실패: {p_data}")

        if not audio_download_url:
            raise HTTPException(status_code=400, detail="Typecast 응답에서 오디오 다운로드 URL을 찾을 수 없습니다.")

        audio_resp = await client.get(audio_download_url)
        output_path.write_bytes(audio_resp.content)
        return {"engine": "typecast", "path": str(output_path)}


async def synthesize_speech_line(
    spoken_text: str,
    engine: str,
    typecast_api_key: str,
    typecast_actor_id: str,
    edge_voice: str,
    speed: float,
    pitch: int,
    emotion: str,
    output_path: Path,
) -> str:
    """
    Synthesizes a single line of spoken_text into output_path.
    If spoken_text is empty (e.g. line was only numbers/symbols and all were excluded),
    generates a 1.2s silent audio clip so the subtitle still displays briefly.
    """
    if not spoken_text.strip():
        generate_fallback_wav(output_path, duration=1.2)
        return "silent"

    if engine == "typecast":
        if not typecast_api_key.strip():
            raise HTTPException(
                status_code=400,
                detail="Typecast API Key가 입력되지 않았습니다. API 키를 입력하거나 로컬 테스트용 Edge-TTS/macOS 음성을 선택해 주세요.",
            )
        if not typecast_actor_id.strip():
            raise HTTPException(
                status_code=400,
                detail="Typecast Actor ID(성우 ID)를 입력해 주세요. (내 성우 목록 불러오기 버튼으로 조회 가능)",
            )
        await synthesize_typecast(
            text=spoken_text,
            api_key=typecast_api_key,
            actor_id=typecast_actor_id,
            speed=speed,
            pitch=pitch,
            emotion=emotion,
            output_path=output_path,
        )
        return "typecast"

    elif engine == "edge":
        # Convert speed (e.g. 1.0 -> +0%, 1.2 -> +20%, 0.8 -> -20%)
        rate_pct = int(round((speed - 1.0) * 100))
        rate_str = f"{rate_pct:+d}%"
        pitch_str = f"{pitch:+d}Hz"
        try:
            communicate = edge_tts.Communicate(
                spoken_text,
                voice=edge_voice or "ko-KR-SunHiNeural",
                rate=rate_str,
                pitch=pitch_str,
            )
            await communicate.save(str(output_path))
            return "edge-tts"
        except Exception:
            # Fallback to macOS `say` if offline
            return synthesize_macos_say(spoken_text, speed, output_path)

    else:
        return synthesize_macos_say(spoken_text, speed, output_path)


def synthesize_macos_say(spoken_text: str, speed: float, output_path: Path) -> str:
    """Uses macOS built-in Korean TTS (`say -v Yuna`) for 100% offline local synthesis."""
    aiff_path = output_path.with_suffix(".aiff")
    wpm = int(185 * max(0.5, min(2.0, speed)))
    try:
        subprocess.run(
            ["say", "-v", "Yuna", "-r", str(wpm), "-o", str(aiff_path), spoken_text],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(aiff_path), "-ar", "44100", "-ac", "1", str(output_path)],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if aiff_path.exists():
            aiff_path.unlink()
        return "Local"
    except Exception:
        est_dur = max(1.5, len(spoken_text) * 0.18)
        generate_fallback_wav(output_path, duration=est_dur)
        return "fallback-silent"


def resolve_font_path(font_id: str) -> str:
    # Check custom uploaded fonts first
    for f in FONTS_DIR.iterdir():
        if f.stem == font_id or f.name == font_id:
            return str(f)
    # Check system fonts
    for sf in DEFAULT_FONTS:
        if sf["id"] == font_id and Path(sf["path"]).exists():
            return sf["path"]
    # Fallback
    for sf in DEFAULT_FONTS:
        if Path(sf["path"]).exists():
            return sf["path"]
    return "/System/Library/Fonts/Supplemental/AppleGothic.ttf"


def render_subtitle_frame_png(
    text: str,
    output_png: Path,
    font_path: str,
    font_size: int = 64,
    text_color: str = "#FFFFFF",
    stroke_color: str = "#000000",
    stroke_width: int = 4,
    shadow_enabled: bool = True,
    shadow_color: str = "#000000",
    shadow_opacity: float = 0.75,
    shadow_offset_x: int = 4,
    shadow_offset_y: int = 6,
    shadow_blur: int = 8,
    bg_box_enabled: bool = False,
    bg_box_color: str = "#000000",
    bg_box_opacity: float = 0.55,
    bg_box_padding_x: int = 32,
    bg_box_padding_y: int = 16,
    bg_box_radius: int = 14,
    y_position_pct: float = 84.0,
    max_width_px: int = 1640,
    canvas_width: int = 1920,
    canvas_height: int = 1080,
):
    """
    Renders a single 1920x1080 RGBA transparent PNG containing the styled subtitle
    with exact drop shadow, Gaussian blur, outline stroke, and optional background box.
    """
    canvas = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    if not text.strip():
        canvas.save(output_png, "PNG")
        return

    try:
        font = ImageFont.truetype(font_path, font_size)
    except Exception:
        font = ImageFont.load_default()

    draw_measure = ImageDraw.Draw(canvas)

    # Word/character wrapping to fit max_width_px
    lines = []
    for raw_line in text.split("\n"):
        words = raw_line.split(" ")
        current = ""
        for w in words:
            candidate = f"{current} {w}".strip() if current else w
            bbox = draw_measure.textbbox((0, 0), candidate, font=font, stroke_width=stroke_width)
            if (bbox[2] - bbox[0]) <= max_width_px:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)

    wrapped_text = "\n".join(lines)
    line_spacing = int(font_size * 0.28)

    bbox = draw_measure.multiline_textbbox(
        (0, 0),
        wrapped_text,
        font=font,
        spacing=line_spacing,
        align="center",
        stroke_width=stroke_width,
    )
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]

    center_x = canvas_width // 2
    center_y = int(canvas_height * (y_position_pct / 100.0))
    text_x = center_x - (text_w // 2) - bbox[0]
    text_y = center_y - (text_h // 2) - bbox[1]

    # 1. Optional Background Box
    if bg_box_enabled:
        box_layer = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
        box_draw = ImageDraw.Draw(box_layer)
        box_rect = [
            center_x - (text_w // 2) - bg_box_padding_x,
            center_y - (text_h // 2) - bg_box_padding_y,
            center_x + (text_w // 2) + bg_box_padding_x,
            center_y + (text_h // 2) + bg_box_padding_y,
        ]
        box_rgba = hex_to_rgba(bg_box_color, bg_box_opacity)
        box_draw.rounded_rectangle(box_rect, radius=bg_box_radius, fill=box_rgba)
        canvas = Image.alpha_composite(canvas, box_layer)

    # 2. Drop Shadow Layer (with Gaussian Blur + X/Y Offset)
    if shadow_enabled and shadow_opacity > 0:
        shadow_layer = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
        shadow_draw = ImageDraw.Draw(shadow_layer)
        s_rgba = hex_to_rgba(shadow_color, shadow_opacity)
        shadow_draw.multiline_text(
            (text_x + shadow_offset_x, text_y + shadow_offset_y),
            wrapped_text,
            font=font,
            fill=s_rgba,
            stroke_width=stroke_width,
            stroke_fill=s_rgba if stroke_width > 0 else None,
            spacing=line_spacing,
            align="center",
        )
        if shadow_blur > 0:
            shadow_layer = shadow_layer.filter(ImageFilter.GaussianBlur(radius=shadow_blur))
        canvas = Image.alpha_composite(canvas, shadow_layer)

    # 3. Main Foreground Text + Outline Stroke
    fg_layer = Image.new("RGBA", (canvas_width, canvas_height), (0, 0, 0, 0))
    fg_draw = ImageDraw.Draw(fg_layer)
    t_rgba = hex_to_rgba(text_color, 1.0)
    st_rgba = hex_to_rgba(stroke_color, 1.0) if stroke_width > 0 else None

    fg_draw.multiline_text(
        (text_x, text_y),
        wrapped_text,
        font=font,
        fill=t_rgba,
        stroke_width=stroke_width,
        stroke_fill=st_rgba,
        spacing=line_spacing,
        align="center",
    )
    canvas = Image.alpha_composite(canvas, fg_layer)
    canvas.save(output_png, "PNG")


def format_srt_timestamp(seconds: float) -> str:
    ms = int(round((seconds % 1) * 1000))
    total_sec = int(seconds)
    s = total_sec % 60
    m = (total_sec // 60) % 60
    h = total_sec // 3600
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def format_vtt_timestamp(seconds: float) -> str:
    return format_srt_timestamp(seconds).replace(",", ".")


# --- API Models ---

class ScriptPreviewRequest(BaseModel):
    script: str
    exclude_numbers: bool = False
    exclude_special: bool = False
    custom_exclude_chars: str = ""


class TypecastVoiceCheckRequest(BaseModel):
    api_key: str


class RenderVideoRequest(BaseModel):
    script: str
    spoken_lines: Optional[List[str]] = None
    no_voice: bool = False
    line_duration_sec: float = 2.0
    tts_engine: str = "edge"  # "typecast", "edge", "macos"
    typecast_api_key: str = ""
    typecast_actor_id: str = ""
    typecast_emotion: str = "normal-1"
    edge_voice: str = "ko-KR-SunHiNeural"
    speed: float = 1.0
    pitch: int = 0
    line_pause_sec: float = 0.25
    exclude_numbers: bool = False
    exclude_special: bool = False
    custom_exclude_chars: str = ""
    # Subtitle Styling
    font_id: str = "system-apple-sd"
    font_size: int = 64
    text_color: str = "#ECEFF4"
    stroke_color: str = "#2E3440"
    stroke_width: int = 4
    shadow_enabled: bool = True
    shadow_color: str = "#2E3440"
    shadow_opacity: float = 0.75
    shadow_offset_x: int = 4
    shadow_offset_y: int = 6
    shadow_blur: int = 8
    bg_box_enabled: bool = False
    bg_box_color: str = "#2E3440"
    bg_box_opacity: float = 0.65
    bg_box_padding_x: int = 32
    bg_box_padding_y: int = 16
    bg_box_radius: int = 14
    y_position_pct: float = 84.0
    # Output format: "mov" (ProRes 4444 alpha), "webm" (VP9 alpha), or "both"
    export_format: str = "both"


class ExportSrtRequest(BaseModel):
    segments: List[Dict[str, Any]]


# --- Endpoints ---

@app.get("/api/fonts")
async def list_fonts():
    fonts = []
    for sf in DEFAULT_FONTS:
        if Path(sf["path"]).exists():
            fonts.append({
                "id": sf["id"],
                "name": sf["name"],
                "url": None,
                "is_custom": False,
            })
    for f in sorted(FONTS_DIR.iterdir()):
        if f.suffix.lower() in (".ttf", ".otf", ".ttc"):
            fonts.append({
                "id": f.name,
                "name": f"{f.stem} ({f.suffix.upper().lstrip('.')})",
                "url": f"/fonts/{f.name}",
                "is_custom": True,
            })
    return {"fonts": fonts}


@app.post("/api/fonts/upload")
async def upload_font(file: UploadFile = File(...)):
    ext = Path(file.filename).suffix.lower()
    if ext not in (".ttf", ".otf", ".ttc"):
        raise HTTPException(status_code=400, detail=".ttf 또는 .otf 폰트 파일만 업로드할 수 있습니다.")
    safe_name = re.sub(r"[^가-힣a-zA-Z0-9._-]", "_", Path(file.filename).name)
    dest = FONTS_DIR / safe_name
    content = await file.read()
    dest.write_bytes(content)
    return {
        "id": safe_name,
        "name": f"{dest.stem} ({ext.upper().lstrip('.')})",
        "url": f"/fonts/{safe_name}",
        "is_custom": True,
    }


@app.post("/api/script/preview-lines")
async def preview_script_lines(req: ScriptPreviewRequest):
    raw_lines = [line.strip() for line in req.script.splitlines() if line.strip()]
    items = []
    for idx, line in enumerate(raw_lines):
        spoken = sanitize_spoken_text(
            line,
            exclude_numbers=req.exclude_numbers,
            exclude_special=req.exclude_special,
            custom_exclude_chars=req.custom_exclude_chars,
        )
        items.append({
            "index": idx + 1,
            "display_text": line,
            "spoken_text": spoken,
            "modified": line != spoken,
        })
    return {"lines": items, "count": len(items)}


@app.post("/api/typecast/actors")
async def fetch_typecast_actors(req: TypecastVoiceCheckRequest):
    clean_key = req.api_key.strip()
    if not clean_key:
        raise HTTPException(status_code=400, detail="Typecast API Key를 입력해 주세요.")

    endpoints = [
        ("https://api.typecast.ai/v3/voices", {"X-API-KEY": clean_key, "Accept": "application/json"}),
        ("https://api.typecast.ai/v2/voices", {"X-API-KEY": clean_key, "Accept": "application/json"}),
        ("https://api.typecast.ai/v1/voices", {"X-API-KEY": clean_key, "Accept": "application/json"}),
        ("https://typecast.ai/api/actor", {"Authorization": f"Bearer {clean_key}", "X-API-KEY": clean_key, "Accept": "application/json"}),
        ("https://api.typecast.ai/v1/actors", {"Authorization": f"Bearer {clean_key}", "X-API-KEY": clean_key, "Accept": "application/json"}),
    ]

    last_status = None
    last_body = ""
    async with httpx.AsyncClient(timeout=15.0) as client:
        for url, hdrs in endpoints:
            try:
                resp = await client.get(url, headers=hdrs)
                last_status = resp.status_code
                if resp.status_code == 200:
                    data = resp.json()
                    if isinstance(data, list):
                        actors_raw = data
                    elif isinstance(data, dict):
                        actors_raw = (
                            data.get("voices")
                            or data.get("result")
                            or data.get("actors")
                            or data.get("data")
                            or []
                        )
                    else:
                        actors_raw = []

                    if isinstance(actors_raw, list) and len(actors_raw) > 0:
                        actors = []
                        for a in actors_raw:
                            if not isinstance(a, dict):
                                continue
                            vid = a.get("voice_id") or a.get("actor_id") or a.get("id") or ""
                            if not vid:
                                continue

                            raw_name = a.get("voice_name") or a.get("name") or "Actor"
                            if isinstance(raw_name, dict):
                                disp_name = (
                                    raw_name.get("kor")
                                    or raw_name.get("ko")
                                    or raw_name.get("eng")
                                    or raw_name.get("en")
                                    or next(iter(raw_name.values()), "Actor")
                                )
                            else:
                                disp_name = str(raw_name)

                            models_field = a.get("models")
                            if isinstance(models_field, list):
                                vers = [
                                    m.get("version")
                                    for m in models_field
                                    if isinstance(m, dict) and m.get("version")
                                ]
                                if vers:
                                    _typecast_voice_models[vid] = vers
                            elif isinstance(a.get("model"), str):
                                _typecast_voice_models[vid] = [a["model"]]

                            lang = a.get("language") or a.get("gender") or "ko"
                            actors.append({
                                "actor_id": vid,
                                "name": disp_name,
                                "language": lang,
                            })
                        if actors:
                            return {"actors": actors}
                else:
                    last_body = resp.text[:200]
            except Exception as e:
                last_body = str(e)
                continue

    err_hint = f" (HTTP {last_status}: {last_body})" if last_status else ""
    raise HTTPException(
        status_code=400,
        detail=f"Typecast 성우 목록을 불러오지 못했습니다{err_hint}. API Key를 확인하거나 Actor ID를 직접 입력해 주세요.",
    )


@app.post("/api/tts/render")
async def render_tts_transparent_video(req: RenderVideoRequest):
    raw_lines = [line.strip() for line in req.script.splitlines() if line.strip()]
    if not raw_lines:
        raise HTTPException(status_code=400, detail="대본을 한 줄 이상 입력해 주세요.")

    job_id = uuid.uuid4().hex[:10]
    job_dir = OUTPUTS_DIR / f"job_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)

    font_path = resolve_font_path(req.font_id)
    timeline = []
    current_time = 0.0
    used_engine = req.tts_engine

    # Pause clip if line_pause_sec > 0
    pause_wav = job_dir / "pause.wav"
    if req.line_pause_sec > 0:
        generate_fallback_wav(pause_wav, duration=req.line_pause_sec)

    audio_concat_list = job_dir / "audio_concat.txt"
    video_concat_list = job_dir / "video_concat.txt"
    audio_entries = []
    video_entries = []

    # Blank transparent PNG for pauses
    blank_png = job_dir / "blank.png"
    Image.new("RGBA", (1920, 1080), (0, 0, 0, 0)).save(blank_png, "PNG")

    for idx, display_line in enumerate(raw_lines):
        if req.spoken_lines is not None and idx < len(req.spoken_lines):
            spoken_line = req.spoken_lines[idx].strip()
        else:
            spoken_line = sanitize_spoken_text(
                display_line,
                exclude_numbers=req.exclude_numbers,
                exclude_special=req.exclude_special,
                custom_exclude_chars=req.custom_exclude_chars,
            )

        raw_audio_path = job_dir / f"line_{idx:03d}_raw.mp3"
        norm_wav_path = job_dir / f"line_{idx:03d}.wav"
        frame_png_path = job_dir / f"frame_{idx:03d}.png"

        if req.no_voice:
            used_engine = "no-voice (자막 전용)"
            dur = max(0.5, float(req.line_duration_sec))
            generate_fallback_wav(norm_wav_path, duration=dur)
        else:
            used_engine = await synthesize_speech_line(
                spoken_text=spoken_line,
                engine=req.tts_engine,
                typecast_api_key=req.typecast_api_key,
                typecast_actor_id=req.typecast_actor_id,
                edge_voice=req.edge_voice,
                speed=req.speed,
                pitch=req.pitch,
                emotion=req.typecast_emotion,
                output_path=raw_audio_path,
            )

            # Normalize to 44.1kHz mono WAV for seamless concat
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", str(raw_audio_path),
                    "-ar", "44100",
                    "-ac", "1",
                    "-c:a", "pcm_s16le",
                    str(norm_wav_path),
                ],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            dur = get_audio_duration(norm_wav_path)

        # Render 1920x1080 transparent subtitle frame PNG
        render_subtitle_frame_png(
            text=display_line,
            output_png=frame_png_path,
            font_path=font_path,
            font_size=req.font_size,
            text_color=req.text_color,
            stroke_color=req.stroke_color,
            stroke_width=req.stroke_width,
            shadow_enabled=req.shadow_enabled,
            shadow_color=req.shadow_color,
            shadow_opacity=req.shadow_opacity,
            shadow_offset_x=req.shadow_offset_x,
            shadow_offset_y=req.shadow_offset_y,
            shadow_blur=req.shadow_blur,
            bg_box_enabled=req.bg_box_enabled,
            bg_box_color=req.bg_box_color,
            bg_box_opacity=req.bg_box_opacity,
            bg_box_padding_x=req.bg_box_padding_x,
            bg_box_padding_y=req.bg_box_padding_y,
            bg_box_radius=req.bg_box_radius,
            y_position_pct=req.y_position_pct,
        )

        start_t = current_time
        end_t = start_t + dur

        # Per-line split outputs (Enter-separated individual audio & transparent video clips)
        line_num = idx + 1
        line_audio_url = None if req.no_voice else f"/outputs/job_{job_id}/{norm_wav_path.name}"
        line_png_url = f"/outputs/job_{job_id}/{frame_png_path.name}"
        line_webm_url = None
        line_mov_url = None

        if req.export_format in ("webm", "both"):
            line_webm_path = job_dir / f"line_{line_num:03d}_alpha.webm"
            l_webm_cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-t", f"{dur:.4f}", "-i", str(frame_png_path),
            ]
            if not req.no_voice:
                l_webm_cmd += ["-i", str(norm_wav_path)]
            l_webm_cmd += [
                "-vf", "fps=30,format=yuva420p",
                "-c:v", "libvpx-vp9",
                "-pix_fmt", "yuva420p",
                "-b:v", "2M",
                "-auto-alt-ref", "0",
            ]
            if req.no_voice:
                l_webm_cmd += ["-an", str(line_webm_path)]
            else:
                l_webm_cmd += ["-c:a", "libopus", "-shortest", str(line_webm_path)]
            subprocess.run(l_webm_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            line_webm_url = f"/outputs/job_{job_id}/{line_webm_path.name}"

        if req.export_format in ("mov", "both"):
            line_mov_path = job_dir / f"line_{line_num:03d}_alpha.mov"
            l_mov_cmd = [
                "ffmpeg", "-y",
                "-loop", "1", "-t", f"{dur:.4f}", "-i", str(frame_png_path),
            ]
            if not req.no_voice:
                l_mov_cmd += ["-i", str(norm_wav_path)]
            l_mov_cmd += [
                "-vf", "fps=30,format=yuva444p10le",
                "-c:v", "prores_ks",
                "-profile:v", "4444",
                "-pix_fmt", "yuva444p10le",
            ]
            if req.no_voice:
                l_mov_cmd += ["-an", str(line_mov_path)]
            else:
                l_mov_cmd += ["-c:a", "pcm_s16le", "-shortest", str(line_mov_path)]
            subprocess.run(l_mov_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            line_mov_url = f"/outputs/job_{job_id}/{line_mov_path.name}"

        timeline.append({
            "index": line_num,
            "display_text": display_line,
            "spoken_text": spoken_line,
            "start": round(start_t, 3),
            "end": round(end_t, 3),
            "duration": round(dur, 3),
            "audio_url": line_audio_url,
            "png_url": line_png_url,
            "webm_url": line_webm_url,
            "mov_url": line_mov_url,
        })

        audio_entries.append(f"file '{norm_wav_path.name}'")
        video_entries.append(f"file '{frame_png_path.name}'\nduration {dur:.4f}")

        current_time = end_t

        # Optional inter-line pause
        if req.line_pause_sec > 0 and idx < len(raw_lines) - 1:
            audio_entries.append(f"file '{pause_wav.name}'")
            video_entries.append(f"file '{blank_png.name}'\nduration {req.line_pause_sec:.4f}")
            current_time += req.line_pause_sec

    # FFmpeg concat demuxer requires the last image repeated without duration
    if video_entries:
        last_png = frame_png_path.name
        video_entries.append(f"file '{last_png}'")

    audio_concat_list.write_text("\n".join(audio_entries) + "\n", encoding="utf-8")
    video_concat_list.write_text("\n".join(video_entries) + "\n", encoding="utf-8")

    # Merge master WAV audio
    master_wav = job_dir / f"tts_audio_{job_id}.wav"
    subprocess.run(
        [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(audio_concat_list),
            "-c:a", "pcm_s16le",
            str(master_wav),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Generate SRT file as well
    srt_lines = []
    for seg in timeline:
        srt_lines.append(
            f"{seg['index']}\n"
            f"{format_srt_timestamp(seg['start'])} --> {format_srt_timestamp(seg['end'])}\n"
            f"{seg['display_text']}\n"
        )
    srt_path = job_dir / f"subtitles_{job_id}.srt"
    srt_path.write_text("\n".join(srt_lines), encoding="utf-8")

    # Create ZIP bundle of all Enter-separated individual clips (Audio + Transparent Video + PNG)
    split_zip_path = job_dir / f"split_lines_bundle_{job_id}.zip"
    with zipfile.ZipFile(split_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.write(srt_path, arcname=srt_path.name)
        for seg in timeline:
            i_num = seg["index"]
            safe_snippet = re.sub(r"[^가-힣a-zA-Z0-9]", "_", seg["display_text"])[:18].strip("_") or f"line_{i_num:03d}"
            prefix = f"{i_num:02d}_{safe_snippet}"
            if not req.no_voice:
                wav_f = job_dir / f"line_{i_num - 1:03d}.wav"
                if wav_f.exists():
                    zf.write(wav_f, arcname=f"audio/{prefix}.wav")
            png_f = job_dir / f"frame_{i_num - 1:03d}.png"
            if png_f.exists():
                zf.write(png_f, arcname=f"png/{prefix}.png")
            mov_f = job_dir / f"line_{i_num:03d}_alpha.mov"
            if mov_f.exists():
                zf.write(mov_f, arcname=f"video_mov/{prefix}.mov")
            webm_f = job_dir / f"line_{i_num:03d}_alpha.webm"
            if webm_f.exists():
                zf.write(webm_f, arcname=f"video_webm/{prefix}.webm")

    outputs = {
        "job_id": job_id,
        "used_engine": used_engine,
        "no_voice": req.no_voice,
        "total_duration": round(current_time, 2),
        "audio_url": None if req.no_voice else f"/outputs/job_{job_id}/{master_wav.name}",
        "srt_url": f"/outputs/job_{job_id}/{srt_path.name}",
        "split_zip_url": f"/outputs/job_{job_id}/{split_zip_path.name}",
        "mov_url": None,
        "webm_url": None,
        "timeline": timeline,
    }

    # 1. Transparent WebM (VP9 + Alpha) - works natively in Chrome/HTML5 video player & OBS/Premiere
    if req.export_format in ("webm", "both"):
        webm_path = job_dir / f"transparent_16x9_{job_id}.webm"
        webm_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(video_concat_list),
        ]
        if not req.no_voice:
            webm_cmd += ["-i", str(master_wav)]
        webm_cmd += [
            "-vf", "fps=30,format=yuva420p",
            "-c:v", "libvpx-vp9",
            "-pix_fmt", "yuva420p",
            "-b:v", "2M",
            "-auto-alt-ref", "0",
        ]
        if req.no_voice:
            webm_cmd += ["-an", str(webm_path)]
        else:
            webm_cmd += ["-c:a", "libopus", "-shortest", str(webm_path)]

        subprocess.run(
            webm_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        outputs["webm_url"] = f"/outputs/job_{job_id}/{webm_path.name}"

    # 2. Transparent MOV (Apple ProRes 4444 with Alpha) - industry standard for Premiere Pro / Final Cut / DaVinci
    if req.export_format in ("mov", "both"):
        mov_path = job_dir / f"transparent_16x9_{job_id}.mov"
        mov_cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(video_concat_list),
        ]
        if not req.no_voice:
            mov_cmd += ["-i", str(master_wav)]
        mov_cmd += [
            "-vf", "fps=30,format=yuva444p10le",
            "-c:v", "prores_ks",
            "-profile:v", "4444",
            "-pix_fmt", "yuva444p10le",
        ]
        if req.no_voice:
            mov_cmd += ["-an", str(mov_path)]
        else:
            mov_cmd += ["-c:a", "pcm_s16le", "-shortest", str(mov_path)]

        subprocess.run(
            mov_cmd,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        outputs["mov_url"] = f"/outputs/job_{job_id}/{mov_path.name}"

    return outputs


# --- Feature 2: Video/Audio Speech Recognition (STT) & Subtitle Extraction ---

_whisper_models: Dict[str, Any] = {}


def get_whisper_model(model_size: str):
    from faster_whisper import WhisperModel
    if model_size not in _whisper_models:
        try:
            _whisper_models[model_size] = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
                download_root=str(MODELS_DIR),
                local_files_only=True,
            )
        except Exception:
            _whisper_models[model_size] = WhisperModel(
                model_size,
                device="cpu",
                compute_type="int8",
                download_root=str(MODELS_DIR),
            )
    return _whisper_models[model_size]


def load_wav_16k_float32(wav_path: Path):
    """Loads a 16kHz mono 16-bit PCM WAV file into a float32 numpy array for faster-whisper."""
    import wave
    import numpy as np

    with wave.open(str(wav_path), "rb") as wf:
        raw_frames = wf.readframes(wf.getnframes())
    return np.frombuffer(raw_frames, dtype=np.int16).astype(np.float32) / 32768.0


def _compute_p90_rms(audio_slice, sr: int = 16000) -> float:
    import numpy as np

    if len(audio_slice) == 0:
        return 0.0
    frame_len = max(1, int(sr * 0.1))
    n_frames = len(audio_slice) // frame_len
    if n_frames <= 0:
        return float(np.sqrt(np.mean(np.square(audio_slice))))
    framed = audio_slice[: n_frames * frame_len].reshape(n_frames, frame_len)
    rms_per_frame = np.sqrt(np.mean(np.square(framed), axis=1))
    return float(np.percentile(rms_per_frame, 90))


def _find_quietest_split_sample(audio_np, target_sample: int, search_radius_samples: int, sr: int = 16000) -> int:
    import numpy as np

    total = len(audio_np)
    lo = max(0, target_sample - search_radius_samples)
    hi = min(total, target_sample + search_radius_samples)
    if hi - lo < int(sr * 0.2):
        return max(0, min(total, target_sample))

    win = int(sr * 0.08)
    step = int(sr * 0.04)
    best_pos = target_sample
    best_rms = float("inf")
    for pos in range(lo, max(lo + 1, hi - win), step):
        seg = audio_np[pos : pos + win]
        rms = float(np.mean(np.square(seg)))
        if rms < best_rms:
            best_rms = rms
            best_pos = pos + win // 2
    return best_pos


def build_stt_audio_chunks(audio_np, sr: int = 16000) -> List[tuple]:
    """
    Splits arbitrarily long 16kHz audio into contiguous speech chunks (<= 20s each)
    so that:
      1. Silero VAD LSTM state is reset every 180s and never saturates on long videos.
      2. Non-contiguous chunks are NEVER concatenated together (preventing faster-whisper's
         single_timestamp_ending from skipping 30s of concatenated speech and preventing
         SpeechTimestampsMap timestamp drift).
      3. Any gaps (> 1.5s) missed by Silero VAD that still contain audible energy are
         automatically included as fallback chunks so recognition never drops out mid-video.
    Returns list of (start_sample, end_sample, is_vad_speech).
    """
    total_samples = len(audio_np)
    if total_samples == 0:
        return []

    max_chunk_sec = 18.0
    max_chunk_samples = int(max_chunk_sec * sr)
    vad_window_samples = int(180.0 * sr)

    vad_speeches: List[Dict[str, int]] = []
    try:
        from faster_whisper.vad import VadOptions, get_speech_timestamps

        vad_opts = VadOptions(
            threshold=0.35,
            min_silence_duration_ms=400,
            speech_pad_ms=250,
            max_speech_duration_s=max_chunk_sec,
        )
        for win_start in range(0, total_samples, vad_window_samples):
            win_end = min(total_samples, win_start + vad_window_samples)
            win_audio = audio_np[win_start:win_end]
            if len(win_audio) < int(0.1 * sr):
                continue
            raw_chunks = get_speech_timestamps(win_audio, vad_opts, sampling_rate=sr)
            for ch in raw_chunks:
                s = max(0, win_start + int(ch["start"]))
                e = min(total_samples, win_start + int(ch["end"]))
                if e > s:
                    vad_speeches.append({"start": s, "end": e})
    except Exception:
        vad_speeches = []

    # Merge closely spaced VAD intervals up to max_chunk_samples
    merged_vad: List[Dict[str, int]] = []
    merge_gap_samples = int(0.35 * sr)
    for ch in vad_speeches:
        if not merged_vad:
            merged_vad.append(dict(ch))
        else:
            prev = merged_vad[-1]
            if ch["start"] <= prev["end"] + merge_gap_samples and (ch["end"] - prev["start"]) <= max_chunk_samples:
                prev["end"] = max(prev["end"], ch["end"])
            else:
                if ch["start"] < prev["end"]:
                    ch = {"start": prev["end"], "end": max(prev["end"], ch["end"])}
                if ch["end"] > ch["start"]:
                    merged_vad.append(ch)

    # Enforce max_chunk_samples on any long VAD interval by splitting at quietest points
    bounded_vad: List[tuple] = []
    for ch in merged_vad:
        cur = ch["start"]
        end = ch["end"]
        while end - cur > max_chunk_samples:
            split_pt = _find_quietest_split_sample(
                audio_np,
                cur + int(15.0 * sr),
                int(2.5 * sr),
                sr=sr,
            )
            if split_pt <= cur + int(1.0 * sr) or split_pt >= end - int(0.5 * sr):
                split_pt = cur + int(15.0 * sr)
            bounded_vad.append((cur, split_pt, True))
            cur = split_pt
        if end > cur:
            bounded_vad.append((cur, end, True))

    # Inspect uncovered gaps (> 1.5s) and recover any regions with audible energy
    all_chunks: List[tuple] = []
    cursor = 0
    min_gap_samples = int(1.5 * sr)
    fallback_win_samples = int(15.0 * sr)

    gaps_to_check: List[tuple] = []
    for s, e, is_vad in bounded_vad:
        if s - cursor >= min_gap_samples:
            gaps_to_check.append((cursor, s))
        all_chunks.append((s, e, is_vad))
        cursor = max(cursor, e)
    if total_samples - cursor >= min_gap_samples:
        gaps_to_check.append((cursor, total_samples))

    for g_start, g_end in gaps_to_check:
        cur = g_start
        while cur < g_end:
            if g_end - cur <= max_chunk_samples:
                sub_end = g_end
            else:
                sub_end = _find_quietest_split_sample(
                    audio_np,
                    cur + fallback_win_samples,
                    int(2.0 * sr),
                    sr=sr,
                )
                if sub_end <= cur + int(1.0 * sr) or sub_end > g_end:
                    sub_end = min(g_end, cur + fallback_win_samples)
            if sub_end - cur >= int(0.25 * sr):
                if _compute_p90_rms(audio_np[cur:sub_end], sr=sr) > 0.0025:
                    all_chunks.append((cur, sub_end, False))
            cur = sub_end

    all_chunks.sort(key=lambda x: x[0])
    return all_chunks


@app.post("/api/stt/transcribe")
async def transcribe_media(
    file: UploadFile = File(...),
    language: str = Form("ko"),
    model_size: str = Form("base"),
    exclude_numbers: bool = Form(False),
    exclude_special: bool = Form(False),
):
    job_id = uuid.uuid4().hex[:10]
    job_dir = OUTPUTS_DIR / f"stt_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)

    ext = Path(file.filename).suffix or ".mp4"
    input_media_path = job_dir / f"source_media{ext}"
    content = await file.read()
    input_media_path.write_bytes(content)

    # Extract 16kHz mono WAV for Whisper
    wav_16k = job_dir / "extracted_16k.wav"
    try:
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", str(input_media_path),
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                str(wav_16k),
            ],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"영상에서 오디오를 추출하지 못했습니다: {e}")

    try:
        sr = 16000
        model = get_whisper_model(model_size)
        lang_arg = None if language == "auto" else language
        audio_np = load_wav_16k_float32(wav_16k)
        total_duration = round(len(audio_np) / float(sr), 2)
        detected_lang = language if language != "auto" else "ko"

        chunks = build_stt_audio_chunks(audio_np, sr=sr)
        segments = []

        for c_start, c_end, is_vad_speech in chunks:
            chunk_offset_sec = c_start / float(sr)
            chunk_audio = audio_np[c_start:c_end]
            chunk_dur = len(chunk_audio) / float(sr)
            if chunk_dur < 0.15:
                continue

            local_offset_sec = 0.0
            max_passes = 6
            pass_num = 0

            while local_offset_sec < chunk_dur - 0.25 and pass_num < max_passes:
                pass_num += 1
                sub_start_sample = int(local_offset_sec * sr)
                sub_audio = chunk_audio[sub_start_sample:]
                sub_dur = len(sub_audio) / float(sr)
                if sub_dur < 0.2:
                    break

                segments_gen, info = model.transcribe(
                    sub_audio,
                    language=lang_arg,
                    beam_size=5,
                    vad_filter=False,
                    condition_on_previous_text=False,
                    word_timestamps=True,
                    no_speech_threshold=0.75 if is_vad_speech else 0.6,
                    log_prob_threshold=-1.0,
                    compression_ratio_threshold=2.4,
                )

                if lang_arg is None and getattr(info, "language", None):
                    detected_lang = info.language
                    lang_arg = detected_lang
                elif getattr(info, "language", None):
                    detected_lang = info.language

                sub_segments = list(segments_gen)
                last_local_end = 0.0

                for seg in sub_segments:
                    last_local_end = max(last_local_end, float(seg.end))

                    # Filter out likely BGM hallucinations in non-VAD fallback gaps
                    if not is_vad_speech:
                        if getattr(seg, "no_speech_prob", 0.0) > 0.65 and getattr(seg, "avg_logprob", 0.0) < -0.7:
                            continue
                        if getattr(seg, "compression_ratio", 1.0) > 2.2:
                            continue

                    text_val = seg.text.strip()
                    if exclude_numbers or exclude_special:
                        text_val = sanitize_spoken_text(
                            text_val,
                            exclude_numbers=exclude_numbers,
                            exclude_special=exclude_special,
                        )
                    if not text_val:
                        continue

                    abs_start = round(chunk_offset_sec + local_offset_sec + float(seg.start), 3)
                    abs_end = round(chunk_offset_sec + local_offset_sec + float(seg.end), 3)
                    if abs_end <= abs_start:
                        abs_end = round(abs_start + 0.5, 3)

                    words_payload = []
                    for w in (getattr(seg, "words", None) or []):
                        w_str = getattr(w, "word", "")
                        if not w_str or not w_str.strip():
                            continue
                        w_start = round(chunk_offset_sec + local_offset_sec + float(w.start), 3)
                        w_end = round(chunk_offset_sec + local_offset_sec + float(w.end), 3)
                        if w_end < w_start:
                            w_end = w_start
                        words_payload.append({
                            "word": w_str,
                            "start": w_start,
                            "end": w_end,
                        })

                    segments.append({
                        "index": len(segments) + 1,
                        "start": abs_start,
                        "end": abs_end,
                        "start_srt": format_srt_timestamp(abs_start),
                        "end_srt": format_srt_timestamp(abs_end),
                        "text": text_val,
                        "words": words_payload,
                    })

                # If Whisper stopped early inside the chunk (e.g. single_timestamp_ending),
                # check if the remaining tail of the chunk still has speech energy and continue.
                remaining_dur = sub_dur - last_local_end
                if last_local_end > 0.25 and remaining_dur > 1.8:
                    tail_start_sample = int((local_offset_sec + last_local_end + 0.08) * sr)
                    tail_audio = chunk_audio[tail_start_sample:]
                    if _compute_p90_rms(tail_audio, sr=sr) > 0.0035:
                        local_offset_sec += last_local_end + 0.05
                        continue
                break
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Whisper 음성 인식 중 오류가 발생했습니다 ({model_size}): {str(e)}",
        )

    # Save SRT, VTT, TXT
    files_info = save_subtitle_files(job_dir, job_id, segments)

    return {
        "job_id": job_id,
        "detected_language": detected_lang,
        "duration": total_duration,
        "media_url": f"/outputs/stt_{job_id}/{input_media_path.name}",
        "segments": segments,
        **files_info,
    }


def save_subtitle_files(job_dir: Path, job_id: str, segments: List[Dict[str, Any]]) -> dict:
    srt_blocks = []
    vtt_blocks = ["WEBVTT\n"]
    txt_lines = []

    for i, s in enumerate(segments):
        idx = i + 1
        start_sec = float(s.get("start", 0.0))
        end_sec = float(s.get("end", start_sec + 2.0))
        text = str(s.get("text", "")).strip()

        srt_blocks.append(
            f"{idx}\n{format_srt_timestamp(start_sec)} --> {format_srt_timestamp(end_sec)}\n{text}\n"
        )
        vtt_blocks.append(
            f"{idx}\n{format_vtt_timestamp(start_sec)} --> {format_vtt_timestamp(end_sec)}\n{text}\n"
        )
        txt_lines.append(text)

    srt_file = job_dir / f"extracted_{job_id}.srt"
    vtt_file = job_dir / f"extracted_{job_id}.vtt"
    txt_file = job_dir / f"extracted_{job_id}.txt"

    srt_file.write_text("\n".join(srt_blocks), encoding="utf-8")
    vtt_file.write_text("\n".join(vtt_blocks), encoding="utf-8")
    txt_file.write_text("\n".join(txt_lines), encoding="utf-8")

    return {
        "srt_url": f"/outputs/{job_dir.name}/{srt_file.name}",
        "vtt_url": f"/outputs/{job_dir.name}/{vtt_file.name}",
        "txt_url": f"/outputs/{job_dir.name}/{txt_file.name}",
    }


@app.post("/api/stt/export")
async def export_edited_subtitles(req: ExportSrtRequest):
    job_id = uuid.uuid4().hex[:8]
    job_dir = OUTPUTS_DIR / f"edited_{job_id}"
    job_dir.mkdir(parents=True, exist_ok=True)
    return save_subtitle_files(job_dir, job_id, req.segments)


# Mount static directories
app.mount("/outputs", StaticFiles(directory=str(OUTPUTS_DIR)), name="outputs")
app.mount("/fonts", StaticFiles(directory=str(FONTS_DIR)), name="fonts")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
async def index():
    return FileResponse(str(STATIC_DIR / "index.html"))


if __name__ == "__main__":
    import threading
    import uvicorn

    port = int(os.environ.get("PORT", "8765"))
    url = f"http://127.0.0.1:{port}"
    threading.Timer(1.2, lambda: webbrowser.open(url)).start()
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")

