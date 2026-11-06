import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "spotify.db")


def load_local_env():
    env_path = os.path.join(BASE_DIR, ".env")
    if not os.path.isfile(env_path):
        return

    with open(env_path, encoding="utf-8") as env_file:
        for line in env_file:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip("\"'"))


load_local_env()
DATABASE_URL = os.getenv("DATABASE_URL")
USE_POSTGRES = bool(DATABASE_URL)
if os.getenv("VERCEL") and not USE_POSTGRES:
    raise RuntimeError("Configura DATABASE_URL en Vercel para usar PostgreSQL.")

try:
    import psycopg
    from psycopg.rows import dict_row
except ImportError:
    psycopg = None
    dict_row = None

DATABASE_ERRORS = (sqlite3.Error,)
if psycopg is not None:
    DATABASE_ERRORS += (psycopg.Error,)


def connect_database():
    if not USE_POSTGRES:
        return sqlite3.connect(DB_PATH)

    if psycopg is None:
        raise RuntimeError(
            "Falta psycopg. Instala las dependencias con "
            "'python -m pip install -r requirements.txt'."
        )
    return psycopg.connect(DATABASE_URL, row_factory=dict_row)


def ensure_schema(conn):
    if USE_POSTGRES:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS tracks (
                id TEXT PRIMARY KEY,
                name TEXT,
                artist TEXT,
                popularity INTEGER,
                danceability DOUBLE PRECISION,
                energy DOUBLE PRECISION,
                valence DOUBLE PRECISION,
                tempo DOUBLE PRECISION
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS play_history (
                play_id TEXT PRIMARY KEY,
                track_id TEXT,
                name TEXT,
                artist TEXT,
                played_at TIMESTAMPTZ
            )
            """
        )
        return

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS tracks (
            id TEXT PRIMARY KEY,
            name TEXT,
            artist TEXT,
            popularity INTEGER,
            danceability REAL,
            energy REAL,
            valence REAL,
            tempo REAL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS play_history (
            play_id TEXT PRIMARY KEY,
            track_id TEXT,
            name TEXT,
            artist TEXT,
            played_at TIMESTAMP
        )
        """
    )
