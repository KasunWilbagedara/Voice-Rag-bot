import io
import re
import asyncio
import urllib.parse
import logging
from typing import Optional, Dict

import requests
import openai
from google import genai
from google.genai import types

from backend.config import get_api_key, is_gemini_key

logger = logging.getLogger("voicerag.audio")

# In-memory LRU-style cache for audio synthesis
_AUDIO_CACHE: Dict[str, bytes] = {}
_MAX_CACHE_ENTRIES = 200


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    custom_api_key: Optional[str] = None,
    language: str = "si",
) -> str:
    """Transcribes user speech with high accuracy and ultra-low latency using active Gemini or OpenAI models."""
    api_key = get_api_key(custom_api_key)

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        # Prioritize active ultra-fast lightweight models first
        models_to_try = [
            "gemini-3.5-flash-lite",
            "gemini-flash-lite-latest",
            "gemini-3.5-flash",
            "gemini-3.6-flash",
        ]

        prompt_text = (
            "Transcribe this audio recording exactly into Sinhala script or English text. Output ONLY the transcribed text without any extra filler."
            if language == "si"
            else "Transcribe this spoken audio recording exactly into text. Output ONLY the transcribed text."
        )

        mime_type = "audio/webm"
        if filename.endswith(".mp3"):
            mime_type = "audio/mp3"
        elif filename.endswith(".wav"):
            mime_type = "audio/wav"

        audio_part = types.Part.from_bytes(
            data=audio_bytes,
            mime_type=mime_type,
        )

        last_error = None
        for m_name in models_to_try:
            try:
                res = client.models.generate_content(
                    model=m_name,
                    contents=[audio_part, prompt_text],
                )
                if res and res.text and res.text.strip():
                    return res.text.strip()
            except Exception as e:
                last_error = e
                logger.debug(f"Transcription model {m_name} failed: {e}")
                continue

        raise RuntimeError(f"Google GenAI audio transcription failed: {last_error}")
    else:
        client = openai.OpenAI(api_key=api_key)
        audio_file = (filename, audio_bytes, "audio/webm")
        params = {
            "model": "whisper-1",
            "file": audio_file,
        }
        if language and language != "auto":
            params["language"] = language

        res = client.audio.transcriptions.create(**params)
        return res.text or ""


def clean_text_for_speech(text: str, language: str = "si") -> str:
    """Strips markdown code blocks, tables, citations, and special symbols for natural human speech."""
    if not text:
        return ""

    cleaned = text

    # Remove JSON code blocks and markdown blocks
    cleaned = re.sub(r"```[\s\S]*?```", " ", cleaned)
    cleaned = re.sub(r"`([^`]+)`", r"\1", cleaned)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"\[\s*Source\s*\d+[^\]]*\]", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\(\s*Source\s*\d+[^)]*\)", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\[\d+\]", "", cleaned)
    cleaned = re.sub(r"^[#]{1,6}\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"__([^_]+)__", r"\1", cleaned)
    cleaned = re.sub(r"_([^_]+)_", r"\1", cleaned)
    cleaned = re.sub(r"~~([^~]+)~~", r"\1", cleaned)

    # Convert markdown bullet lists to natural conversational pauses
    cleaned = re.sub(r"^\s*[-*•]\s+", ", ", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\s*\d+\.\s+", ", ", cleaned, flags=re.MULTILINE)

    if language == "si":
        cleaned = cleaned.replace("%", " ප්‍රතිශතය ")
        cleaned = cleaned.replace("&", " සහ ")
        cleaned = cleaned.replace("+", " එකතු කිරීම ")
        cleaned = cleaned.replace("=", " සමාන වේ ")
        cleaned = cleaned.replace("@", " ඇට් ")
    else:
        cleaned = cleaned.replace("%", " percent ")
        cleaned = cleaned.replace("&", " and ")
        cleaned = cleaned.replace("+", " plus ")
        cleaned = cleaned.replace("=", " equals ")
        cleaned = cleaned.replace("@", " at ")

    cleaned = re.sub(r"[\`~^<>\\|{}\[\]]", " ", cleaned)
    cleaned = re.sub(r"\n+", ". ", cleaned)
    cleaned = re.sub(r"\s+,", ",", cleaned)
    cleaned = re.sub(r"\s+\.", ".", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()

    return cleaned


def extract_conversational_voice_summary(text: str, language: str = "si", max_sentences: int = 2) -> str:
    """
    Extracts a concise, punchy 1-2 sentence spoken summary suitable for low-latency speech synthesis.
    The full detailed text (with tables, charts, and bullet points) is shown on screen.
    """
    cleaned = clean_text_for_speech(text, language)
    if not cleaned:
        return ""

    # Split into sentences based on punctuation (. ! ? or Sinhala full stop)
    sentences = re.split(r"(?<=[.!?෴])\s+", cleaned)
    selected = []
    total_len = 0

    for s in sentences:
        s_clean = s.strip()
        if not s_clean:
            continue
        # Skip sentences that look like pure table headings or metadata
        if s_clean.startswith("|") or "---" in s_clean:
            continue
        selected.append(s_clean)
        total_len += len(s_clean)
        if len(selected) >= max_sentences or total_len >= 180:
            break

    if selected:
        res = " ".join(selected)
        if not res.endswith((".", "!", "?", "෴")):
            res += "."
        return res

    # Fallback to first 160 characters
    return cleaned[:160] + "..." if len(cleaned) > 160 else cleaned


def resolve_neural_voice(voice: str, language: str = "si") -> str:
    """Maps user persona selection to high-quality Microsoft Neural human voices."""
    v = (voice or "").lower().strip()

    if language == "si":
        if v in ["sameera", "male", "onyx", "echo"]:
            return "si-LK-SameeraNeural"
        return "si-LK-ThiliniNeural"  # Default natural female voice for Sinhala
    else:
        if v in ["andrew", "male", "echo", "onyx"]:
            return "en-US-AndrewNeural"
        elif v in ["emma"]:
            return "en-US-EmmaNeural"
        elif v in ["brian"]:
            return "en-US-BrianNeural"
        elif v in ["aria"]:
            return "en-US-AriaNeural"
        return "en-US-AvaNeural"  # Default natural female voice for English


async def generate_edge_neural_tts_async(
    text: str,
    voice_name: str,
    speed: float = 1.0,
) -> bytes:
    """Direct asynchronous Edge Neural speech generation."""
    import edge_tts

    # Format rate for Edge TTS, e.g. "+15%" or "-10%"
    rate_percent = int(round((speed - 1.0) * 100))
    rate_str = f"{rate_percent:+d}%"

    communicate = edge_tts.Communicate(text, voice_name, rate=rate_str)
    audio_buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.extend(chunk["data"])

    return bytes(audio_buffer)


async def generate_speech_audio_async(
    text: str,
    voice: str = "thilini",
    custom_api_key: Optional[str] = None,
    language: str = "si",
    speed: float = 1.0,
) -> bytes:
    """Asynchronously generates high-fidelity neural voice audio with caching."""
    clean_text = clean_text_for_speech(text, language)
    if not clean_text:
        raise ValueError("No speakable text remaining after cleaning.")

    # Check in-memory audio cache
    cache_key = f"{language}_{voice}_{round(speed, 2)}_{hash(clean_text)}"
    if cache_key in _AUDIO_CACHE:
        return _AUDIO_CACHE[cache_key]

    api_key = get_api_key(custom_api_key)

    # 1. OpenAI HD Studio Voices (if custom OpenAI key is provided and requested)
    if not is_gemini_key(api_key):
        try:
            client = openai.OpenAI(api_key=api_key)
            valid_voice = voice if voice in ["alloy", "echo", "fable", "onyx", "nova", "shimmer"] else "nova"
            mp3_response = client.audio.speech.create(
                model="tts-1-hd",
                voice=valid_voice,
                input=clean_text,
                response_format="mp3",
                speed=max(0.75, min(speed, 1.25)),
            )
            audio_bytes = mp3_response.content
            if len(_AUDIO_CACHE) < _MAX_CACHE_ENTRIES:
                _AUDIO_CACHE[cache_key] = audio_bytes
            return audio_bytes
        except Exception as e:
            logger.warning(f"OpenAI TTS issue: {e}")

    # 2. Microsoft Edge Neural Voices (Fastest ~0.8s, natural, lifelike, studio grade)
    neural_voice = resolve_neural_voice(voice, language)
    try:
        audio_bytes = await generate_edge_neural_tts_async(clean_text, neural_voice, speed)
        if audio_bytes and len(audio_bytes) > 500:
            if len(_AUDIO_CACHE) < _MAX_CACHE_ENTRIES:
                _AUDIO_CACHE[cache_key] = audio_bytes
            return audio_bytes
    except Exception as e:
        logger.warning(f"Edge Neural TTS failed: {e}")

    # 3. Fallback to gTTS
    try:
        from gtts import gTTS
        lang_code = "si" if language == "si" else "en"
        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        audio_bytes = fp.read()
        if len(_AUDIO_CACHE) < _MAX_CACHE_ENTRIES:
            _AUDIO_CACHE[cache_key] = audio_bytes
        return audio_bytes
    except Exception as e:
        logger.warning(f"gTTS fallback failed: {e}")

    # 4. Final web fallback
    encoded_text = urllib.parse.quote(clean_text[:200])
    lang_code = "si" if language == "si" else "en"
    url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl={lang_code}&client=gtx"
    res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
    if res.status_code == 200:
        return res.content

    raise RuntimeError("Failed to generate TTS audio across all available engines.")


def generate_speech_audio(
    text: str,
    voice: str = "thilini",
    custom_api_key: Optional[str] = None,
    language: str = "si",
    speed: float = 1.0,
) -> bytes:
    """Synchronous wrapper for generate_speech_audio_async."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                return executor.submit(
                    asyncio.run,
                    generate_speech_audio_async(text, voice, custom_api_key, language, speed),
                ).result()
        else:
            return loop.run_until_complete(
                generate_speech_audio_async(text, voice, custom_api_key, language, speed)
            )
    except RuntimeError:
        return asyncio.run(
            generate_speech_audio_async(text, voice, custom_api_key, language, speed)
        )
