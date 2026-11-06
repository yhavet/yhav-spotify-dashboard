# Spotify Analytics

FastAPI y un dashboard para explorar el historial reciente de Spotify. El proyecto
usa SQLite local si no existe `DATABASE_URL`, o PostgreSQL (por ejemplo Neon) si
la variable está configurada.

## Configuración

1. Crea una base PostgreSQL en Neon y copia su cadena de conexión. Para producción,
   usa la URL pooled que ofrece Neon.
2. Copia `.env.example` a `.env` y completa las credenciales de Spotify y
   `DATABASE_URL`. No publiques ese archivo.
3. Instala las dependencias:

   ```powershell
   .\.venv-1\Scripts\python.exe -m pip install -r requirements.txt
   ```

4. Migra las tablas `tracks` y `play_history` desde `spotify.db`:

   ```powershell
   .\.venv-1\Scripts\python.exe migrate_to_postgres.py
   ```

   La migración es repetible y no duplica filas. Conserva `spotify.db` como
   respaldo local.

5. Inicia el dashboard local, que ya leerá PostgreSQL:

   ```powershell
   .\.venv-1\Scripts\python.exe -m uvicorn main:app --reload
   ```

6. Ejecuta `index.py` localmente para consultar Spotify y guardar nuevas
   reproducciones en la misma base PostgreSQL.

Para desplegar la API, configura las mismas variables (`DATABASE_URL`,
`SPOTIFY_CLIENT_ID` y `SPOTIFY_CLIENT_SECRET`) como variables de entorno del
servicio de hosting. No incluyas `.env`, `.cache` ni `spotify.db` en el despliegue.
