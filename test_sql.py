import sqlite3

conn = sqlite3.connect("spotify.db")
cursor = conn.cursor()


cursor.execute(
    """
    SELECT name, artist, popularity, danceability, energy, valence, tempo
    FROM tracks
    """
)


resultados = cursor.fetchall()

print(f"--- Total de registros encontrados: {len(resultados)} ---")
for fila in resultados:
    print(fila)

conn.close()