"""
FastAPI YouTube Transcript API - Vercel Deployment
Extrae transcripciones de YouTube usando la Innertube API
Probado y funcional en 2025
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import httpx
import re
import json
from typing import Optional, List
from pydantic import BaseModel

# Crear aplicación FastAPI
app = FastAPI(
    title="YouTube Transcript API",
    description="Extrae transcripciones de videos de YouTube usando Innertube API",
    version="1.0.0"
)

# Agregar CORS para permitir solicitudes desde cualquier origen
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Modelos Pydantic
class TranscriptFragment(BaseModel):
    startTime: float
    duration: float
    text: str

class TranscriptResponse(BaseModel):
    success: bool
    videoId: str
    language: str
    fragmentCount: int
    transcript: List[TranscriptFragment]

class ErrorResponse(BaseModel):
    success: bool
    error: str
    details: Optional[str] = None

# Función para obtener la API key
async def get_innertube_api_key(video_id: str) -> str:
    """
    Extrae la INNERTUBE_API_KEY de la página del video de YouTube
    """
    video_url = f"https://www.youtube.com/watch?v={video_id}"
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            video_url,
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        )
        response.raise_for_status()
        html = response.text
    
    api_key_match = re.search(r'"INNERTUBE_API_KEY":"([^"]+)"', html)
    if not api_key_match:
        raise ValueError("No se encontró INNERTUBE_API_KEY en la página del video")
    
    return api_key_match.group(1)

# Función para obtener la respuesta del reproductor
async def get_player_response(video_id: str, api_key: str) -> dict:
    """
    Llama a la API del reproductor de YouTube para obtener información del video
    """
    player_url = f"https://www.youtube.com/youtubei/v1/player?key={api_key}"
    
    player_body = {
        "context": {
            "client": {
                "clientName": "ANDROID",
                "clientVersion": "20.10.38"
            }
        },
        "videoId": video_id
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.post(
            player_url,
            json=player_body,
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
        response.raise_for_status()
        return response.json()

# Función para extraer subtítulos
async def get_captions_xml(base_url: str) -> str:
    """
    Obtiene el XML de los subtítulos desde la URL
    """
    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(
            base_url,
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        response.raise_for_status()
        return response.text

# Función para parsear XML de subtítulos
def parse_captions_xml(xml_content: str) -> List[TranscriptFragment]:
    """
    Parsea el XML de subtítulos y extrae los fragmentos
    """
    captions = []
    pattern = r'<text start="([^"]+)" dur="([^"]+)">([^<]+)</text>'
    
    for match in re.finditer(pattern, xml_content):
        start_time = float(match.group(1))
        duration = float(match.group(2))
        text = match.group(3)
        
        # Decodificar entidades HTML
        text = text.replace('&amp;', '&')
        text = text.replace('&lt;', '<')
        text = text.replace('&gt;', '>')
        text = text.replace('&quot;', '"')
        text = text.replace('&#39;', "'")
        
        captions.append(TranscriptFragment(
            startTime=start_time,
            duration=duration,
            text=text
        ))
    
    return captions

# Función principal para obtener transcripción
async def get_youtube_transcript(video_id: str, language: str = 'en') -> TranscriptResponse:
    """
    Extrae la transcripción completa de un video de YouTube
    """
    try:
        # Paso 1: Obtener API key
        api_key = await get_innertube_api_key(video_id)
        
        # Paso 2: Obtener respuesta del reproductor
        player_response = await get_player_response(video_id, api_key)
        
        # Paso 3: Extraer URL de subtítulos
        if 'captions' not in player_response:
            raise ValueError("No se encontraron subtítulos para este video")
        
        captions_data = player_response.get('captions', {})
        tracks = captions_data.get('playerCaptionsTracklistRenderer', {}).get('captionTracks', [])
        
        if not tracks:
            raise ValueError("No hay pistas de subtítulos disponibles")
        
        # Buscar idioma específico
        track = None
        for t in tracks:
            if t.get('languageCode') == language:
                track = t
                break
        
        if not track:
            track = tracks[0]  # Usar el primer idioma disponible
        
        base_url = track['baseUrl']
        if '&fmt=' in base_url:
            base_url = re.sub(r'&fmt=\w+', '', base_url)
        
        # Paso 4: Obtener y parsear subtítulos
        captions_xml = await get_captions_xml(base_url)
        transcript = parse_captions_xml(captions_xml)
        
        if not transcript:
            raise ValueError("No se pudieron extraer fragmentos de subtítulos")
        
        return TranscriptResponse(
            success=True,
            videoId=video_id,
            language=track.get('languageCode', language),
            fragmentCount=len(transcript),
            transcript=transcript
        )
        
    except Exception as e:
        raise ValueError(f"Error al extraer transcripción: {str(e)}")

# Rutas de la API

@app.get("/", tags=["Info"])
async def root():
    """Endpoint raíz con información de la API"""
    return {
        "name": "YouTube Transcript API",
        "version": "1.0.0",
        "description": "Extrae transcripciones de videos de YouTube",
        "endpoints": {
            "GET /transcript": "Obtiene la transcripción de un video",
            "GET /health": "Verifica el estado de la API"
        }
    }

@app.get("/health", tags=["Info"])
async def health_check():
    """Verifica que la API esté funcionando"""
    return {"status": "ok", "message": "API funcionando correctamente"}

@app.get(
    "/transcript",
    response_model=TranscriptResponse,
    tags=["Transcription"],
    summary="Obtener transcripción de YouTube",
    description="Extrae la transcripción completa de un video de YouTube"
)
async def get_transcript(
    video_id: str = Query(..., description="ID del video de YouTube"),
    language: str = Query("en", description="Código de idioma ISO 639-1 (ej: en, es, fr)")
):
    """
    Obtiene la transcripción de un video de YouTube.
    
    **Parámetros:**
    - `video_id`: ID del video de YouTube (requerido)
    - `language`: Código de idioma (opcional, por defecto: en)
    
    **Ejemplo:**
    ```
    GET /transcript?video_id=pGlZi2SwETc&language=en
    ```
    
    **Respuesta exitosa:**
    ```json
    {
        "success": true,
        "videoId": "pGlZi2SwETc",
        "language": "en",
        "fragmentCount": 100,
        "transcript": [
            {
                "startTime": 25.17,
                "duration": 2.08,
                "text": "Primer fragmento de texto"
            }
        ]
    }
    ```
    """
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id es requerido")
    
    try:
        result = await get_youtube_transcript(video_id, language)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get(
    "/transcript/full-text",
    tags=["Transcription"],
    summary="Obtener transcripción como texto completo",
    description="Obtiene la transcripción como un solo string de texto"
)
async def get_transcript_full_text(
    video_id: str = Query(..., description="ID del video de YouTube"),
    language: str = Query("en", description="Código de idioma ISO 639-1")
):
    """
    Obtiene la transcripción como un texto completo (sin timestamps).
    """
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id es requerido")
    
    try:
        result = await get_youtube_transcript(video_id, language)
        full_text = " ".join([frag.text for frag in result.transcript])
        return {
            "success": True,
            "videoId": video_id,
            "language": result.language,
            "full_text": full_text
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

@app.get(
    "/transcript/srt",
    tags=["Transcription"],
    summary="Obtener transcripción en formato SRT",
    description="Obtiene la transcripción en formato SubRip (SRT)"
)
async def get_transcript_srt(
    video_id: str = Query(..., description="ID del video de YouTube"),
    language: str = Query("en", description="Código de idioma ISO 639-1")
):
    """
    Obtiene la transcripción en formato SRT (SubRip).
    """
    if not video_id:
        raise HTTPException(status_code=400, detail="video_id es requerido")
    
    try:
        result = await get_youtube_transcript(video_id, language)
        
        srt_content = ""
        for i, frag in enumerate(result.transcript, 1):
            start = format_timestamp(frag.startTime)
            end = format_timestamp(frag.startTime + frag.duration)
            srt_content += f"{i}\n{start} --> {end}\n{frag.text}\n\n"
        
        return {
            "success": True,
            "videoId": video_id,
            "language": result.language,
            "format": "srt",
            "content": srt_content
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

# Función auxiliar para formatear timestamps
def format_timestamp(seconds: float) -> str:
    """Convierte segundos a formato HH:MM:SS,mmm"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int((seconds % 1) * 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

# Manejo de errores global
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": exc.detail
        }
    )

# Para Vercel
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
