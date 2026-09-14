import time
import base64
import logging
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Response
from pydantic import BaseModel

from backend.audio_service import (
    transcribe_audio,
    generate_speech_audio_async,
    extract_conversational_voice_summary,
)
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
    voice: Optional[str] = "thilini"
    apiKey: Optional[str] = None
    language: Optional[str] = "si"
    speed: Optional[float] = 1.0


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
async def text_to_speech(req: TtsRequest):
    if not req.text or not req.text.strip():
        raise HTTPException(status_code=400, detail="Text string is required.")

    try:
        audio_bytes = await generate_speech_audio_async(
            text=req.text,
            voice=req.voice or "thilini",
            custom_api_key=req.apiKey,
            language=req.language or "si",
            speed=req.speed or 1.0,
        )
        return Response(
            content=audio_bytes,
            media_type="audio/mpeg",
            headers={
                "Cache-Control": "public, max-age=3600",
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
    voice: Optional[str] = Form("thilini"),
    model: Optional[str] = Form("gemini-3.5-flash-lite"),
    provider: Optional[str] = Form(None),
    baseUrl: Optional[str] = Form(None),
    language: Optional[str] = Form("si"),
    speed: Optional[float] = Form(1.0),
):
    """
    Unified low-latency Voice-RAG pipeline:
    1. Speech-to-Text (STT) via ultra-fast Gemini Flash Lite
    2. Hybrid Cross-Lingual Vector & DB RAG Retrieval
    3. Complete AI Answer Generation
    4. Voice-Optimized Conversational Summary generation
    5. High-fidelity Neural Speech Synthesis on the conversational summary (under ~0.8s)
    """
    total_t0 = time.time()
    try:
        audio_bytes = await audio.read()
        if not audio_bytes:
            raise HTTPException(status_code=400, detail="No audio file provided.")

        max_audio_size = 25 * 1024 * 1024  # 25 MB
        if len(audio_bytes) > max_audio_size:
            raise HTTPException(status_code=413, detail="Audio file size exceeds maximum allowed limit of 25MB.")

        # 1. Speech-to-Text
        stt_t0 = time.time()
        user_query_text = transcribe_audio(
            audio_bytes=audio_bytes,
            filename=audio.filename or "recording.webm",
            custom_api_key=apiKey,
            language=language or "si",
        )
        stt_duration = round(time.time() - stt_t0, 2)

        if not user_query_text or not user_query_text.strip():
            raise HTTPException(
                status_code=422,
                detail="Could not transcribe any speech from recording.",
            )

        # 2. Cross-Lingual Vector & BM25 Hybrid Search
        rag_t0 = time.time()
        query_embedding = get_embedding(user_query_text, apiKey)
        retrieved_chunks = search_vector_database(
            query_embedding=query_embedding,
            top_k=6,
            query_text=user_query_text,
            custom_api_key=apiKey,
        )

        # 3. LLM Answer Generation
        # Default to gemini-3.5-flash-lite for lowest latency
        active_model = model or "gemini-3.5-flash-lite"
        rag_res = generate_voice_rag_answer(
            user_query=user_query_text,
            retrieved_chunks=retrieved_chunks,
            custom_api_key=apiKey,
            model_name=active_model,
            target_language=language or "si",
            provider=provider,
            base_url=baseUrl,
        )
        rag_duration = round(time.time() - rag_t0, 2)

        ai_response_text = rag_res["answer"]
        final_chunks = rag_res["retrievedChunks"]

        # 4. Save Chat History
        save_chat_history(user_query_text, final_chunks, ai_response_text)

        # 5. Extract Voice-Optimized Spoken Summary (1-2 sentences for instant low-latency speech)
        voice_spoken_text = extract_conversational_voice_summary(
            ai_response_text,
            language=language or "si",
            max_sentences=2,
        )

        # 6. High-Fidelity Neural Text-to-Speech
        tts_t0 = time.time()
        audio_base64 = None
        try:
            tts_audio_bytes = await generate_speech_audio_async(
                text=voice_spoken_text or ai_response_text,
                voice=voice or "thilini",
                custom_api_key=apiKey,
                language=language or "si",
                speed=speed or 1.0,
            )
            audio_base64 = base64.b64encode(tts_audio_bytes).decode("utf-8")
        except Exception as tts_err:
            logger.warning(f"Voice pipeline TTS generation note: {tts_err}")
        tts_duration = round(time.time() - tts_t0, 2)

        total_duration = round(time.time() - total_t0, 2)

        return {
            "userQueryText": user_query_text,
            "aiResponseText": ai_response_text,
            "voiceSpokenText": voice_spoken_text,
            "retrievedChunks": final_chunks,
            "audioBase64": audio_base64,
            "audioFormat": "audio/mp3",
            "latency": {
                "stt": stt_duration,
                "rag": rag_duration,
                "tts": tts_duration,
                "total": total_duration,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unified Voice Pipeline Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
