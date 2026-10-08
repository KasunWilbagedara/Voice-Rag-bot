"""
Human-Like Speech Audio Service (STT & Expressive Neural TTS).

Features:
1. Multi-Stage Speech Normalization (strips markdown, formats phone digits, expands symbols & numbers).
2. Human-Like Expressive Neural Voices (Microsoft Ava/Andrew Multilingual & Thilini/Sameera).
3. OpenAI Studio TTS Integration (tts-1-hd with alloy, nova, shimmer, echo).
4. Cadence & Pitch Shaping: Relaxed conversational speaking rate (-4%) and natural warm pitch (+1Hz).
5. Robust Fallback Pipeline: OpenAI HD -> Microsoft Edge Neural -> Google Cloud -> gTTS.
"""

import io
import re
import os
import asyncio
import logging
from typing import Optional, Dict

import requests
import openai
from google import genai
from google.genai import types

from backend_pure_rag.config import get_api_key, is_gemini_key

logger = logging.getLogger("pure_rag.audio")

_AUDIO_CACHE: Dict[str, bytes] = {}
_MAX_CACHE_ENTRIES = 200


# =====================================================================
# 1. PHONETIC SPEECH TEXT NORMALIZER
# =====================================================================

def normalize_text_for_speech(text: str, language: str = "si") -> str:
    """
    Transforms written text and markdown into clean, natural human-spoken words.
    Removes syntax that causes TTS to stutter or sound robotic.
    """
    if not text:
        return ""

    # 1. Strip code blocks, json, and markdown tables
    cleaned = re.sub(r"```[\s\S]*?```", "", text)
    cleaned = re.sub(r"\|[^\n]+\|", "", cleaned)
    cleaned = re.sub(r"^#{1,6}\s+.*$", "", cleaned, flags=re.MULTILINE)

    # 2. Strip bold, italic, and bullet characters
    cleaned = re.sub(r"\*\*([^*]+)\*\*", r"\1", cleaned)
    cleaned = re.sub(r"\*([^*]+)\*", r"\1", cleaned)
    cleaned = re.sub(r"^[*\-+]\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"^\d+\.\s+", "", cleaned, flags=re.MULTILINE)
    cleaned = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", cleaned)
    cleaned = re.sub(r"[`_~>]", "", cleaned)

    # 3. Phonetic spacing for phone numbers (prevents reading '1717' as 'seventeen seventeen')
    cleaned = re.sub(r"\b1717\b", "1 7 1 7", cleaned)
    cleaned = re.sub(r"(\+94\s*\d{2})\s*(\d{3})\s*(\d{4})", r"\1 \2 \3", cleaned)

    # 4. Expand symbols into conversational spoken phrases
    if language == "si":
        cleaned = re.sub(r"(\d+(\.\d+)?)%", r"සියයට \1", cleaned)
        cleaned = re.sub(r"&", "සහ", cleaned)
        cleaned = re.sub(r"\bSLA\b", "එස් එල් ඒ", cleaned)
        cleaned = re.sub(r"\bSLT\b", "එස් එල් ටී", cleaned)
        cleaned = re.sub(r"\bGbps\b", "ගිගාබිට්ස් පර් සෙකන්ඩ්", cleaned)
    else:
        cleaned = re.sub(r"%", " percent", cleaned)
        cleaned = re.sub(r"&", " and ", cleaned)
        cleaned = re.sub(r"\bGbps\b", "gigabits per second", cleaned)
        cleaned = re.sub(r"\bSLA\b", "S L A", cleaned)

    # 5. Clean up multiple whitespaces and excessive punctuation
    cleaned = re.sub(r"[;:]", ",", cleaned)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned


def extract_conversational_voice_summary(full_text: str, language: str = "si", max_sentences: int = 2) -> str:
    """Extracts the first 1-2 natural conversational spoken sentences for instant low-latency audio synthesis."""
    if not full_text:
        return ""

    normalized = normalize_text_for_speech(full_text, language)
    paragraphs = [p.strip() for p in normalized.split("\n\n") if p.strip()]
    first_para = paragraphs[0] if paragraphs else normalized

    if language == "si":
        sentences = re.split(r"(?<=[.!?|])\s+", first_para)
    else:
        sentences = re.split(r"(?<=[.!?])\s+", first_para)

    selected = sentences[:max_sentences]
    summary = " ".join(selected).strip()
    return summary if summary else first_para[:250].strip()


# =====================================================================
# 2. SPEECH-TO-TEXT (STT) TRANSCRIPTION
# =====================================================================

def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    custom_api_key: Optional[str] = None,
    language: str = "si",
) -> str:
    """Transcribes user speech with high accuracy using Gemini or OpenAI."""
    api_key = get_api_key(custom_api_key)

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
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
                logger.debug(f"Transcription model {m_name} note: {e}")
                continue

        raise RuntimeError(f"Gemini speech-to-text failed: {last_error}")
    else:
        client = openai.OpenAI(api_key=api_key)
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = filename

        transcription = client.audio.transcriptions.create(
            model="whisper-1",
            file=audio_file,
            language=language if language != "auto" else None,
        )
        return transcription.text.strip()


# =====================================================================
# 3. HIGH-FIDELITY HUMAN NEURAL TTS ENGINES
# =====================================================================

def generate_openai_tts(text: str, voice: str = "nova", speed: float = 1.0, api_key: Optional[str] = None) -> bytes:
    """Uses OpenAI tts-1-hd for studio-grade human natural voice synthesis."""
    resolved_key = api_key or os.getenv("OPENAI_API_KEY")
    if not resolved_key or is_gemini_key(resolved_key):
        return b""

    try:
        client = openai.OpenAI(api_key=resolved_key)
        # Map voice names to valid OpenAI voices (alloy, echo, fable, onyx, nova, shimmer)
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        selected_voice = voice.lower() if voice.lower() in valid_voices else "nova"

        res = client.audio.speech.create(
            model="tts-1-hd",
            voice=selected_voice,
            input=text[:4096],
            speed=speed,
        )
        return res.content
    except Exception as e:
        logger.debug(f"OpenAI TTS note: {e}")
        return b""


async def generate_edge_tts_human(text: str, voice: str = "thilini", language: str = "si", speed: float = 1.0) -> bytes:
    """
    Uses Microsoft Azure Next-Gen Multilingual Neural models with pitch & cadence shaping.
    Sounds vastly more human than robotic TTS.
    """
    try:
        import edge_tts

        # Select natural neural voices with conversational intonation
        if language == "si":
            # Sinhala neural voices
            edge_voice = "si-LK-ThiliniNeural" if voice in ["thilini", "nethmi", "female"] else "si-LK-SameeraNeural"
            # Slightly relaxed conversational pace
            rate_str = f"{int((speed - 1.0) * 100 - 3):+d}%"
            pitch_str = "+1Hz"
        else:
            # English: Use Microsoft's state-of-the-art Multilingual Neural voices
            if voice in ["thilini", "female", "ava", "nova"]:
                edge_voice = "en-US-AvaMultilingualNeural"  # Warm, conversational female
            else:
                edge_voice = "en-US-AndrewMultilingualNeural"  # Articulate, natural male
            rate_str = f"{int((speed - 1.0) * 100 - 4):+d}%"
            pitch_str = "+1Hz"

        communicate = edge_tts.Communicate(text, edge_voice, rate=rate_str, pitch=pitch_str)
        fp = io.BytesIO()
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                fp.write(chunk["data"])
        fp.seek(0)
        return fp.read()
    except Exception as e:
        logger.debug(f"Edge-TTS note: {e}")
        return b""


def generate_google_cloud_tts_sinhala(text: str, voice_name: str = "thilini", speed: float = 1.0) -> bytes:
    """Uses Google Cloud Text-to-Speech API for Sinhala neural voice synthesis."""
    try:
        from google.cloud import texttospeech
        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)
        voice_params = texttospeech.VoiceSelectionParams(
            language_code="si-LK",
            name="si-LK-Standard-A" if voice_name in ["thilini", "nethmi", "female"] else "si-LK-Standard-B",
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=max(0.85, speed * 0.95),  # slightly relaxed pace for human cadence
        )

        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice_params,
            audio_config=audio_config,
        )
        return response.audio_content
    except Exception as e:
        logger.debug(f"Google Cloud TTS note: {e}")
        return b""


def generate_gtts_audio(text: str, lang: str = "si") -> bytes:
    """Emergency fallback TTS using Google Translate web service."""
    try:
        from gtts import gTTS
        clean = re.sub(r"[*_#`]", "", text)
        tts = gTTS(text=clean[:300], lang=lang, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e:
        logger.warning(f"gTTS error: {e}")
        return b""


def generate_google_gemini_tts(
    text: str,
    voice: str = "thilini",
    language: str = "si",
    custom_api_key: Optional[str] = None,
) -> bytes:
    """
    Uses Google's latest Gemini 3.8 Flash TTS model for state-of-the-art human voice synthesis.
    Generates natural breathing sounds, human actor cadence, and emotional warmth.
    Prebuilt voices: Aoede (warm female), Charon (deep male), Puck (upbeat), Kore (gentle), Fenrir (authoritative).
    """
    api_key = get_api_key(custom_api_key)
    if not is_gemini_key(api_key):
        return b""

    voice_lower = (voice or "").lower()
    if voice_lower in ["charon", "male", "sameera", "andrew"]:
        gemini_voice = "Charon"
    elif voice_lower in ["puck", "upbeat"]:
        gemini_voice = "Puck"
    elif voice_lower in ["kore", "calm"]:
        gemini_voice = "Kore"
    elif voice_lower in ["fenrir", "deep"]:
        gemini_voice = "Fenrir"
    else:
        gemini_voice = "Aoede"

    prompt = (
        f"Speak warmly and naturally like a helpful human professional in {'Sinhala (සිංහල)' if language == 'si' else 'English'}: {text}"
    )

    try:
        client = genai.Client(api_key=api_key)
        for model in ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-2.5-flash-preview-tts"]:
            try:
                res = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(
                        response_modalities=["AUDIO"],
                        speech_config=types.SpeechConfig(
                            voice_config=types.VoiceConfig(
                                prebuilt_voice_config=types.PrebuiltVoiceConfig(
                                    voice_name=gemini_voice
                                )
                            )
                        ),
                    ),
                )
                if res and res.candidates:
                    for part in res.candidates[0].content.parts:
                        if part.inline_data and part.inline_data.data:
                            return part.inline_data.data
            except Exception as e:
                logger.debug(f"Google Gemini Flash TTS ({model}) note: {e}")
                continue
    except Exception as e:
        logger.debug(f"Google Gemini TTS client error: {e}")

    return b""


# =====================================================================
# 4. UNIFIED MULTI-ENGINE SPEECH SYNTHESIS PIPELINE
# =====================================================================

async def generate_speech_audio_async(
    text: str,
    voice: str = "thilini",
    custom_api_key: Optional[str] = None,
    language: str = "si",
    speed: float = 1.0,
) -> bytes:
    """
    Generates human-like spoken audio with multi-tier fallbacks:
    1. Phonetic Text Normalization (removes robotic syntax, normalizes digits & symbols)
    2. Google's Latest Gemini Flash Human Actor TTS (Aoede / Charon / Puck -> natural breath & warmth)
    3. OpenAI tts-1-hd (if OpenAI key available -> studio human voice)
    4. Microsoft Multilingual Neural (Ava / Andrew / Thilini / Sameera -> rich natural inflection)
    5. Google Cloud TTS
    6. gTTS fallback
    """
    clean_spoken_text = normalize_text_for_speech(text, language)
    if not clean_spoken_text:
        clean_spoken_text = text

    cache_key = f"{language}_{voice}_{speed}_{hash(clean_spoken_text)}"
    if cache_key in _AUDIO_CACHE:
        return _AUDIO_CACHE[cache_key]

    audio_bytes = b""

    # 1. Try Google's Latest Gemini Flash Human Actor TTS (Aoede, Charon, Puck, Kore, Fenrir)
    audio_bytes = generate_google_gemini_tts(clean_spoken_text, voice=voice, language=language, custom_api_key=custom_api_key)

    # 2. Try OpenAI Studio HD TTS if OpenAI key is provided or present
    if not audio_bytes:
        audio_bytes = generate_openai_tts(clean_spoken_text, voice=voice, speed=speed, api_key=custom_api_key)

    # 3. Try Microsoft Azure Multilingual Neural Models (Ava / Andrew / Thilini)
    if not audio_bytes:
        audio_bytes = await generate_edge_tts_human(clean_spoken_text, voice=voice, language=language, speed=speed)

    # 4. Try Google Cloud TTS for Sinhala
    if not audio_bytes and language == "si":
        audio_bytes = generate_google_cloud_tts_sinhala(clean_spoken_text, voice_name=voice, speed=speed)

    # 5. Fallback to gTTS
    if not audio_bytes:
        audio_bytes = generate_gtts_audio(clean_spoken_text, lang="si" if language == "si" else "en")

    if audio_bytes:
        if len(_AUDIO_CACHE) >= _MAX_CACHE_ENTRIES:
            _AUDIO_CACHE.pop(next(iter(_AUDIO_CACHE)))
        _AUDIO_CACHE[cache_key] = audio_bytes
        return audio_bytes

    raise RuntimeError("All text-to-speech audio engines failed to generate audio stream.")
