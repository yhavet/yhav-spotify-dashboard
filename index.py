import os

import spotipy
from spotipy.exceptions import SpotifyException
from spotipy.oauth2 import SpotifyOAuth

from database import BASE_DIR, USE_POSTGRES, connect_database, ensure_schema


CLIENT_ID = os.getenv("CLIENT_ID") or os.getenv("SPOTIFY_CLIENT_ID")
CLIENT_SECRET = os.getenv("CLIENT_SECRET") or os.getenv("SPOTIFY_CLIENT_SECRET")
REDIRECT_URI = (
    os.getenv("REDIRECT_URI")
    or os.getenv("SPOTIFY_REDIRECT_URI")
    or "http://127.0.0.1:8080"
)
CACHE_PATH = os.path.join(BASE_DIR, ".cache")

if not CLIENT_ID or not CLIENT_SECRET:
    raise SystemExit(
        "Completa CLIENT_ID y CLIENT_SECRET en el archivo .env del proyecto."
    )

sp = spotipy.Spotify(
    auth_manager=SpotifyOAuth(
        client_id=CLIENT_ID,
        client_secret=CLIENT_SECRET,
        redirect_uri=REDIRECT_URI,
        scope="user-read-recently-played",
        cache_path=CACHE_PATH,
        open_browser=True,
    )
)

conn = connect_database()
try:
    ensure_schema(conn)
    cursor = conn.cursor()

    results = sp.current_user_recently_played(limit=50)
    inserted_count = 0
    for item in results["items"]:
        track = item.get("track")
        played_at = item.get("played_at")
        if not track or not track.get("id") or not played_at:
            continue

        track_id = track["id"]
        artist = ", ".join(
            artist_info["name"]
            for artist_info in track.get("artists", [])
            if artist_info.get("name")
        )
        if USE_POSTGRES:
            insert_sql = """
                INSERT INTO play_history (
                    play_id, track_id, name, artist, played_at
                )
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (play_id) DO NOTHING
            """
        else:
            insert_sql = """
                INSERT OR IGNORE INTO play_history (
                    play_id, track_id, name, artist, played_at
                )
                VALUES (?, ?, ?, ?, ?)
            """
        cursor.execute(
            insert_sql,
            (
                f"{track_id}:{played_at}",
                track_id,
                track.get("name"),
                artist,
                played_at,
            ),
        )
        inserted_count += cursor.rowcount

    conn.commit()
    database_name = "PostgreSQL" if USE_POSTGRES else "SQLite local"
    print(
        f"Reproducciones nuevas guardadas: {inserted_count} "
        f"({database_name})."
    )
except SpotifyException as exc:
    if exc.http_status == 403:
        raise SystemExit(
            f"Spotify denegó el acceso (HTTP 403): {exc.msg}"
        ) from exc
    raise SystemExit(
        f"Error de Spotify (HTTP {exc.http_status}): {exc.msg}"
    ) from exc
finally:
    conn.close()
