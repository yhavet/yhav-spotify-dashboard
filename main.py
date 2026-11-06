import json
import os
import logging
import sqlite3
import time

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import requests

from database import (
    BASE_DIR,
    DATABASE_ERRORS,
    USE_POSTGRES,
    connect_database,
)

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Spotify Data Analytics",
    description="Dashboard para explorar el historial de Spotify.",
)

DASHBOARD_PATH = os.path.join(BASE_DIR, "static", "index.html")
STATIC_DIR = os.path.join(BASE_DIR, "static")
SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID") or os.getenv("CLIENT_ID")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET") or os.getenv("CLIENT_SECRET")
SPOTIFY_REFRESH_TOKEN = os.getenv("SPOTIFY_REFRESH_TOKEN")
_spotify_access_token = None
_spotify_access_token_expires_at = 0

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def fetch_rows(query):
    conn = None
    try:
        conn = connect_database()
        if not USE_POSTGRES:
            conn.row_factory = sqlite3.Row
        return [dict(row) for row in conn.execute(query).fetchall()]
    except DATABASE_ERRORS as exc:
        logger.exception("No se pudieron leer datos de la base.")
        raise HTTPException(
            status_code=500,
            detail="No se pudieron leer los datos de la base de datos.",
        ) from exc
    finally:
        if conn is not None:
            conn.close()


@app.get("/", include_in_schema=False)
def dashboard():
    if not os.path.isfile(DASHBOARD_PATH):
        raise HTTPException(status_code=404, detail="No se encontró el dashboard.")
    return FileResponse(DASHBOARD_PATH)


@app.get("/api")
def api_home():
    return {"mensaje": "Bienvenido a la API de Spotify de mi portfolio."}


@app.get("/api/tracks")
def get_tracks():
    tracks = fetch_rows("SELECT * FROM tracks ORDER BY lower(name)")
    return {"total": len(tracks), "tracks": tracks}


@app.get("/api/history")
def get_history():
    history = fetch_rows(
        """
        SELECT play_id, track_id, name, artist, played_at
        FROM play_history
        ORDER BY played_at DESC
        """
    )
    return {"total": len(history), "history": history}


def get_spotify_access_token():
    global _spotify_access_token, _spotify_access_token_expires_at

    if _spotify_access_token and time.monotonic() < _spotify_access_token_expires_at:
        return _spotify_access_token
    refresh_token = SPOTIFY_REFRESH_TOKEN
    if not refresh_token:
        cache_path = os.path.join(BASE_DIR, ".cache")
        try:
            with open(cache_path, encoding="utf-8") as cache_file:
                refresh_token = json.load(cache_file).get("refresh_token")
        except FileNotFoundError:
            pass
        except (OSError, ValueError) as exc:
            logger.exception("No se pudo leer el token local de Spotify.")
            raise HTTPException(
                status_code=500,
                detail="No se pudo leer la autorización local de Spotify.",
            ) from exc

    if not SPOTIFY_CLIENT_ID or not SPOTIFY_CLIENT_SECRET or not refresh_token:
        raise HTTPException(
            status_code=503,
            detail="Falta configurar la conexión de reproducción de Spotify.",
        )

    try:
        response = requests.post(
            "https://accounts.spotify.com/api/token",
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
            },
            auth=(SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET),
            timeout=10,
        )
        response.raise_for_status()
        token_data = response.json()
    except requests.HTTPError as exc:
        status_code = (
            exc.response.status_code
            if exc.response is not None
            else "desconocido"
        )
        logger.warning(
            "Spotify rechazó la renovación del token (HTTP %s).",
            status_code,
        )
        if status_code == 400:
            detail = (
                "Spotify no aceptó el refresh token (HTTP 400). "
                "Vuelve a autorizar la cuenta y actualiza SPOTIFY_REFRESH_TOKEN."
            )
        elif status_code == 401:
            detail = (
                "Spotify no aceptó las credenciales de la aplicación (HTTP 401). "
                "Revisa SPOTIFY_CLIENT_ID y SPOTIFY_CLIENT_SECRET."
            )
        else:
            detail = f"Spotify rechazó la renovación del token (HTTP {status_code})."
        raise HTTPException(status_code=502, detail=detail) from exc
    except requests.RequestException as exc:
        logger.exception("No se pudo renovar el token de Spotify.")
        raise HTTPException(
            status_code=502,
            detail="No se pudo conectar con los servidores de Spotify.",
        ) from exc
    except ValueError as exc:
        logger.exception("Spotify devolvió un token inválido.")
        raise HTTPException(
            status_code=502,
            detail="Spotify devolvió una respuesta de autenticación inválida.",
        ) from exc

    access_token = token_data.get("access_token")
    if not access_token:
        raise HTTPException(
            status_code=502,
            detail="Spotify no devolvió un token de acceso válido.",
        )

    _spotify_access_token = access_token
    _spotify_access_token_expires_at = time.monotonic() + max(
        token_data.get("expires_in", 3600) - 60,
        0,
    )
    return _spotify_access_token


@app.get("/api/now-playing")
def get_now_playing():
    global _spotify_access_token, _spotify_access_token_expires_at

    access_token = get_spotify_access_token()
    try:
        response = requests.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.exception("No se pudo consultar la reproducción actual de Spotify.")
        raise HTTPException(
            status_code=502,
            detail="No se pudo consultar la reproducción actual de Spotify.",
        ) from exc

    if response.status_code == 204:
        return {"is_playing": False, "track": None}
    if response.status_code == 403:
        raise HTTPException(
            status_code=403,
            detail=(
                "Spotify requiere autorizar el permiso "
                "user-read-currently-playing."
            ),
        )
    if response.status_code == 401:
        _spotify_access_token = None
        _spotify_access_token_expires_at = 0
        raise HTTPException(
            status_code=502,
            detail="Spotify rechazó la autorización. Hay que volver a conectar la cuenta.",
        )
    if not response.ok:
        logger.error(
            "Spotify devolvió HTTP %s al consultar la reproducción.",
            response.status_code,
        )
        raise HTTPException(
            status_code=502,
            detail="Spotify no pudo devolver la reproducción actual.",
        )

    try:
        data = response.json()
    except ValueError as exc:
        raise HTTPException(
            status_code=502,
            detail="Spotify devolvió una reproducción inválida.",
        ) from exc

    item = data.get("item")
    if not item:
        return {"is_playing": False, "track": None}

    album = item.get("album") or {}
    artists = item.get("artists") or []
    return {
        "is_playing": bool(data.get("is_playing")),
        "progress_ms": data.get("progress_ms"),
        "track": {
            "name": item.get("name") or "Canción desconocida",
            "artist": ", ".join(
                artist["name"] for artist in artists if artist.get("name")
            ),
            "album_image": next(
                (
                    image.get("url")
                    for image in album.get("images", [])
                    if image.get("url")
                ),
                None,
            ),
            "duration_ms": item.get("duration_ms"),
            "spotify_url": (item.get("external_urls") or {}).get("spotify"),
        },
    }
