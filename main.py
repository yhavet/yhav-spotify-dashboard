import os
import logging
import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

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
