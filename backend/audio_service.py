import io
import re
import asyncio
import urllib.parse
import logging
from typing import Optional

import requests
import openai
from gtts import gTTS
from google import genai
from google.genai import types

from backend.config import get_api_key, is_gemini_key

logger = logging.getLogger("voicerag.audio")


def transcribe_audio(
    audio_bytes: bytes,
    filename: str = "audio.webm",
    custom_api_key: Optional[str] = None,
    language: str = "si",
) -> str:
    api_key = get_api_key(custom_api_key)

    if is_gemini_key(api_key):
        client = genai.Client(api_key=api_key)
        models_to_try = ["gemini-2.0-flash", "gemini-1.5-flash"]

        prompt_text = (
            "Transcribe this audio recording exactly into Sinhala script or English text. Output ONLY the transcribed text."
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

        for m_name in models_to_try:
            try:
                res = client.models.generate_content(
                    model=m_name,
                    contents=[audio_part, prompt_text],
                )
                if res and res.text and res.text.strip():
                    return res.text.strip()
            except Exception:
                continue

        raise RuntimeError("Google GenAI audio transcription failed.")
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
    if not text:
        return ""

    cleaned = text

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


async def _generate_edge_neural_tts(text: str, voice_name: str) -> bytes:
    import edge_tts
    communicate = edge_tts.Communicate(text, voice_name)
    audio_buffer = bytearray()
    async for chunk in communicate.stream():
        if chunk["type"] == "audio":
            audio_buffer.extend(chunk["data"])
    return bytes(audio_buffer)


def generate_google_wavenet_tts(text: str, language: str = "si") -> Optional[bytes]:
    """Generates Google Cloud WaveNet/Neural human voice stream using Google Text-to-Speech service."""
    try:
        from google.cloud import texttospeech
        client = texttospeech.TextToSpeechClient()

        synthesis_input = texttospeech.SynthesisInput(text=text)

        if language == "si":
            voice = texttospeech.VoiceSelectionParams(
                language_code="si-LK",
                name="si-LK-Wavenet-A",
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            )
        else:
            voice = texttospeech.VoiceSelectionParams(
                language_code="en-US",
                name="en-US-Studio-O",
                ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
            )

        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.96,
            pitch=0.0,
        )

        response = client.synthesize_speech(
            input=synthesis_input, voice=voice, audio_config=audio_config
        )
        return response.audio_content
    except Exception as e:
        logger.debug(f"Google Cloud WaveNet client fallback: {e}")
        return None


def generate_speech_audio(
    text: str,
    voice: str = "nova",
    custom_api_key: Optional[str] = None,
    language: str = "si",
    speed: float = 0.95,
) -> bytes:
    api_key = get_api_key(custom_api_key)
    clean_text = clean_text_for_speech(text, language)
    if not clean_text:
        raise ValueError("No speakable text remaining after cleaning.")

    # 1. OpenAI HD Studio Voices (if using OpenAI Key)
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
            return mp3_response.content
        except Exception as e:
            logger.warning(f"OpenAI TTS issue: {e}")

    # 2. Google Cloud Neural WaveNet Human Voice
    google_wavenet_audio = generate_google_wavenet_tts(clean_text, language)
    if google_wavenet_audio:
        return google_wavenet_audio

    # 3. Microsoft Neural Human AI Voices (si-LK-SameeraNeural / si-LK-ThiliniNeural & en-US-AvaMultilingualNeural)
    try:
        if language == "si":
            neural_voice = "si-LK-SameeraNeural" if voice.lower() in ["sameera", "onyx", "echo"] else "si-LK-ThiliniNeural"
        else:
            neural_voice = "en-US-AndrewMultilingualNeural" if voice.lower() in ["onyx", "echo", "sameera"] else "en-US-AvaMultilingualNeural"

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        audio_bytes = loop.run_until_complete(_generate_edge_neural_tts(clean_text, neural_voice))
        loop.close()
        if audio_bytes and len(audio_bytes) > 500:
            return audio_bytes
    except Exception as e:
        logger.warning(f"Edge Neural TTS fallback: {e}")

    # 4. Fallback gTTS
    try:
        lang_code = "si" if language == "si" else "en"
        tts = gTTS(text=clean_text, lang=lang_code, slow=False)
        fp = io.BytesIO()
        tts.write_to_fp(fp)
        fp.seek(0)
        return fp.read()
    except Exception as e:
        encoded_text = urllib.parse.quote(clean_text[:200])
        lang_code = "si" if language == "si" else "en"
        url = f"https://translate.google.com/translate_tts?ie=UTF-8&q={encoded_text}&tl={lang_code}&client=gtx"
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if res.status_code == 200:
            return res.content
        raise RuntimeError(f"Failed to generate TTS audio: {e}")
