from fastapi import FastAPI
from fastapi.responses import JSONResponse
import httpx
import asyncio

app = FastAPI(title="TV Channel Search API")

@app.get("/")
async def root():
    return JSONResponse(
        content={
            "status_code": 400,
            "message": "The search parameter is required to find TV channels by name",
            "developer": "El Impaciente",
            "telegram_channel": "https://t.me/Apisimpacientes",
            "usage": "Use /tv?search=channel_name",
            "examples": [
                "/tv?search=CNN",
                "/tv?search=BBC",
                "/tv?search=ESPN"
            ]
        },
        status_code=400
    )

@app.get("/tv")
async def get_tv_channels(search: str = ""):
    # Validar que search no esté vacío
    if not search or search.strip() == "":
        return JSONResponse(
            content={
                "status_code": 400,
                "message": "The search parameter is required to find TV channels by name",
                "developer": "El Impaciente",
                "telegram_channel": "https://t.me/Apisimpacientes",
                "example": "/tv?search=CNN"
            },
            status_code=400
        )
    
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            # Obtener datos de canales y streams en paralelo
            channels_url = "https://iptv-org.github.io/api/channels.json"
            streams_url = "https://iptv-org.github.io/api/streams.json"
            
            channels_response, streams_response = await asyncio.gather(
                client.get(channels_url),
                client.get(streams_url),
                return_exceptions=True
            )
            
            if isinstance(channels_response, Exception) or channels_response.status_code != 200:
                return JSONResponse(
                    content={
                        "status_code": 400,
                        "message": "Error connecting to TV channels database. Please try again.",
                        "developer": "El Impaciente",
                        "telegram_channel": "https://t.me/Apisimpacientes"
                    },
                    status_code=400
                )
            
            all_channels = channels_response.json()
            all_streams = streams_response.json() if not isinstance(streams_response, Exception) and streams_response.status_code == 200 else []
            
            # Crear un diccionario de streams por channel_id para búsqueda rápida
            streams_by_channel = {}
            for stream in all_streams:
                channel_id = stream.get("channel")
                if channel_id:
                    if channel_id not in streams_by_channel:
                        streams_by_channel[channel_id] = []
                    streams_by_channel[channel_id].append(stream)
            
            # Filtrar canales por nombre (búsqueda case-insensitive)
            search_lower = search.lower()
            filtered_channels = [
                channel for channel in all_channels 
                if search_lower in channel.get("name", "").lower()
            ]
            
            if not filtered_channels:
                return JSONResponse(
                    content={
                        "status_code": 400,
                        "message": f"No TV channels found with name '{search}'. Try searching for popular channels like CNN, BBC, or ESPN.",
                        "developer": "El Impaciente",
                        "telegram_channel": "https://t.me/Apisimpacientes"
                    },
                    status_code=400
                )
            
            # Formatear los primeros 20 resultados con sus streams
            channels = []
            for channel in filtered_channels[:20]:
                channel_id = channel.get("id", "")
                
                # Obtener streams para este canal
                channel_streams = streams_by_channel.get(channel_id, [])
                streams_list = []
                for stream in channel_streams[:5]:  # Limitar a 5 streams por canal
                    streams_list.append({
                        "url": stream.get("url", ""),
                        "title": stream.get("title", ""),
                        "quality": stream.get("quality", ""),
                        "referrer": stream.get("referrer", ""),
                        "user_agent": stream.get("user_agent", "")
                    })
                
                channels.append({
                    "id": channel_id,
                    "name": channel.get("name", "Unknown"),
                    "alt_names": channel.get("alt_names", []),
                    "network": channel.get("network", ""),
                    "country": channel.get("country", ""),
                    "subdivision": channel.get("subdivision", ""),
                    "city": channel.get("city", ""),
                    "broadcast_area": channel.get("broadcast_area", []),
                    "languages": channel.get("languages", []),
                    "categories": channel.get("categories", []),
                    "is_nsfw": channel.get("is_nsfw", False),
                    "launched": channel.get("launched", ""),
                    "closed": channel.get("closed", ""),
                    "replaced_by": channel.get("replaced_by", ""),
                    "website": channel.get("website", ""),
                    "logo": channel.get("logo", ""),
                    "streams": streams_list,
                    "streams_count": len(channel_streams)
                })
            
            # Retornar respuesta exitosa
            return JSONResponse(
                content={
                    "status_code": 200,
                    "message": f"{len(channels)} results found",
                    "developer": "El Impaciente",
                    "telegram_channel": "https://t.me/Apisimpacientes",
                    "search": search,
                    "total_results": len(filtered_channels),
                    "showing": len(channels),
                    "channels": channels
                },
                status_code=200
            )
        
    except httpx.TimeoutException:
        return JSONResponse(
            content={
                "status_code": 400,
                "message": "Request timeout. Please try again.",
                "developer": "El Impaciente",
                "telegram_channel": "https://t.me/Apisimpacientes"
            },
            status_code=400
        )
    except Exception as e:
        return JSONResponse(
            content={
                "status_code": 400,
                "message": "Error getting TV channels. Please try again.",
                "developer": "El Impaciente",
                "telegram_channel": "https://t.me/Apisimpacientes"
            },
            status_code=400
        )
