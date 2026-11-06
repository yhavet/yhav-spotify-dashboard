import sqlite3
import os
from datetime import datetime

import psycopg

from database import BASE_DIR, DATABASE_URL, USE_POSTGRES, ensure_schema

SQLITE_PATH = os.path.join(BASE_DIR, "spotify.db")


def parse_played_at(value):
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def main():
    if not USE_POSTGRES or not DATABASE_URL:
        raise SystemExit(
            "Configura DATABASE_URL en el archivo .env antes de migrar."
        )

    try:
        source = sqlite3.connect(SQLITE_PATH)
    except sqlite3.Error as exc:
        raise SystemExit(f"No se pudo abrir la base local: {exc}") from exc

    try:
        tracks = source.execute(
            """
            SELECT id, name, artist, popularity, danceability, energy, valence, tempo
            FROM tracks
            """
        ).fetchall()
        history = source.execute(
            """
            SELECT play_id, track_id, name, artist, played_at
            FROM play_history
            """
        ).fetchall()
    except sqlite3.Error as exc:
        raise SystemExit(f"No se pudieron leer las tablas de SQLite: {exc}") from exc
    finally:
        source.close()

    try:
        with psycopg.connect(DATABASE_URL) as destination:
            ensure_schema(destination)
            cursor = destination.cursor()
            cursor.executemany(
                """
                INSERT INTO tracks (
                    id, name, artist, popularity, danceability,
                    energy, valence, tempo
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (id) DO NOTHING
                """,
                tracks,
            )
            cursor.executemany(
                """
                INSERT INTO play_history (
                    play_id, track_id, name, artist, played_at
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (play_id) DO NOTHING
                """,
                [
                    (*row[:4], parse_played_at(row[4]))
                    for row in history
                ],
            )
            track_total = destination.execute(
                "SELECT COUNT(*) AS total FROM tracks"
            ).fetchone()[0]
            history_total = destination.execute(
                "SELECT COUNT(*) AS total FROM play_history"
            ).fetchone()[0]
    except psycopg.Error as exc:
        raise SystemExit(
            "No se pudo migrar a PostgreSQL. Revisa DATABASE_URL y la conexión "
            f"a Neon. Detalle: {exc}"
        ) from exc

    print(f"Migración completada: {track_total} canciones y {history_total} reproducciones.")
    print("Puedes volver a ejecutar este script; no duplica registros.")


if __name__ == "__main__":
    main()
