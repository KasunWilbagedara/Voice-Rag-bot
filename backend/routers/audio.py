import base64
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from pydantic import BaseModel

from backend.audio_service import transcribe_audio, generate_speech_audio
from backend.rag_service import (
    get_embedding,
    search_vector_database,
    generate_voice_rag_answer,
    save_chat_history,
)

router = APIRouter(tags=["Audio"])
logger = logging.getLogger("voicerag.audio_router")

class TtsRequest(BaseModel):
    text: str
    voice: Optional[str] = "nova"
    apiKey: Optional[str] = None
    language: Optional[str] = "si"

@router.post("/api/stt")
async def speech_to_text(
    audio: UploadFile = File(...),
    apiKey: Optional[str] = Form(None),
    language: Optional[str] = Form("si"),
):
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="No audio provided.")

        max_audio_size = 25 * 1024 * 1024  # 25 MB
        if len(audio_bytes) > max_audio_size:
            raise HTTPException(status_code=413, detail="Audio file size exceeds maximum allowed limit of 25MB.")

        transcribed_text = transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.webm",
            custom_api_key=apiKey,
            language=language or "si",
        )

        return {"text": transcribed_text}
    except Exception as e:
        logger.error(f"STT API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/tts")
def text_to_speech(req: TtsRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text string is required.")

    try:
        audio_bytes = generate_speech_audio(
            text=req.text,
            voice=req.voice or "nova",
            custom_api_key=req.apiKey,
            language=req.language or "si",
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "no-cache",
                "Content-Length": str(len(audio_bytes)),
            },
        )
    except Exception as e:
        logger.error(f"TTS API Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/api/voice-pipeline")
async def unified_voice_pipeline(
    audio: UploadFile = File(...),
    apiKey: Optional[str] = Form(None),
    voice: Optional[str] = Form("nova"),
    model: Optional[str] = Form("gemini-2.0-flash"),
    language: Optional[str] = Form("si"),
):
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="No audio file provided.")

        max_audio_size = 25 * 1024 * 1024  # 25 MB
        if len(audio_bytes) > max_audio_size:
            raise HTTPException(status_code=413, detail="Audio file size exceeds maximum allowed limit of 25MB.")

        # 1. Speech-to-Text
        user_query_text = transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.webm",
            custom_api_key=apiKey,
            language=language or "si",
        )

        if not user_query_text or not user_query_text.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not transcribe any speech from recording.",
            )

        # 2. Cross-Lingual Vector & BM25 Hybrid Search
        query_embedding = get_embedding(user_query_text, apiKey)
        retrieved_chunks = search_vector_database(
            query_embedding=query_embedding,
            top_k=8,
            query_text=user_query_text,
            custom_api_key=apiKey,
        )

        # 3. LLM Answer Generation (1200 Token Limit -> No Truncation)
        ai_response_text = generate_voice_rag_answer(
            user_query=user_query_text,
            retrieved_chunks=retrieved_chunks,
            custom_api_key=apiKey,
            model_name=model or "gemini-2.0-flash",
            target_language=language or "si",
        )

        # 4. Save Chat History
        save_chat_history(user_query_text, retrieved_chunks, ai_response_text)

        # 5. Text-to-Speech
        audio_base64 = None
        try:
            tts_audio_bytes = generate_speech_audio(
                text=ai_response_text,
                voice=voice or "nova",
                custom_api_key=apiKey,
                language=language or "si",
            )
            audio_base64 = base64.b64encode(tts_audio_bytes).decode("utf-8")
        except Exception as tts_err:
            logger.warning(f"Voice pipeline TTS audio generation fallback: {tts_err}")

        return {
            "userQueryText": user_query_text,
            "aiResponseText": ai_response_text,
            "retrievedChunks": retrieved_chunks,
            "audioBase64": audio_base64,
            "audioFormat": "audio/mp3",
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unified Voice Pipeline Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
