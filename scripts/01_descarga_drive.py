"""
01_descarga_drive.py
====================
Descarga ÚNICA de los GeoTIFFs desde Google Drive al disco local.
Este script se ejecuta UNA SOLA VEZ por integrante del equipo.
Después de la descarga, todos los demás scripts leen desde data/raw/.

Uso:
    python scripts/01_descarga_drive.py
"""

import io
from typing import Optional

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from tqdm import tqdm

from config import PATHS, CONFIG

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


# ── AUTENTICACIÓN ─────────────────────────────────────────────
def autenticar_drive():
    """Autentica con Google Drive usando OAuth2.

    La primera vez abre el navegador para autorizar.
    Las siguientes veces usa el token guardado en token.json.

    Returns:
        Servicio autenticado de Google Drive API.

    Notas:
        Requiere credentials.json descargado desde Google Cloud Console:
        APIs & Services > Credentials > OAuth 2.0 Client ID > Desktop App
    """
    creds: Optional[Credentials] = None

    if PATHS["token"].exists():
        creds = Credentials.from_authorized_user_file(str(PATHS["token"]), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(PATHS["credentials"]), SCOPES
            )
            creds = flow.run_local_server(port=0)
        with open(PATHS["token"], "w") as token:
            token.write(creds.to_json())

    return build("drive", "v3", credentials=creds)


# ── BUSCAR CARPETA EN DRIVE ───────────────────────────────────
def buscar_carpeta(service, nombre: str) -> Optional[str]:
    """Busca el ID de una carpeta en Google Drive por nombre."""
    query = f"name='{nombre}' and mimeType='application/vnd.google-apps.folder' and trashed=false"
    resultado = service.files().list(q=query, fields="files(id, name)").execute()
    archivos = resultado.get("files", [])

    if not archivos:
        print(f"[!] Carpeta '{nombre}' no encontrada en Drive.")
        print("    Verifica que las tareas de GEE terminaron correctamente.")
        return None

    return archivos[0]["id"]


# ── BUSCAR ARCHIVO EN CARPETA ─────────────────────────────────
def buscar_archivo(service, nombre: str, carpeta_id: str) -> Optional[str]:
    """Busca el ID de un archivo dentro de una carpeta de Drive."""
    query = f"name='{nombre}' and '{carpeta_id}' in parents and trashed=false"
    resultado = service.files().list(q=query, fields="files(id, name, size)").execute()
    archivos = resultado.get("files", [])

    if not archivos:
        print(f"  [!] Archivo '{nombre}' no encontrado. ¿Terminó la tarea en GEE?")
        return None

    return archivos[0]["id"]


# ── DESCARGAR ARCHIVO ─────────────────────────────────────────
def descargar_archivo(service, archivo_id: str, destino) -> bool:
    """Descarga un archivo de Drive al disco local con barra de progreso."""
    destino = PATHS["sentinel_2015"].parent / destino.name if hasattr(destino, 'name') else destino

    if destino.exists():
        print(f"  [✓] Ya existe localmente: {destino.name} — omitiendo.")
        return True

    request = service.files().get_media(fileId=archivo_id)
    buffer = io.BytesIO()
    downloader = MediaIoBaseDownload(buffer, request, chunksize=10 * 1024 * 1024)

    print(f"  [↓] Descargando {destino.name}...")
    done = False
    with tqdm(total=100, unit="%", ncols=60) as pbar:
        progreso_anterior = 0
        while not done:
            status, done = downloader.next_chunk()
            if status:
                progreso = int(status.progress() * 100)
                pbar.update(progreso - progreso_anterior)
                progreso_anterior = progreso

    destino.parent.mkdir(parents=True, exist_ok=True)
    with open(destino, "wb") as f:
        f.write(buffer.getvalue())

    print(f"  [✓] Guardado en {destino} ({destino.stat().st_size / 1e6:.1f} MB)")
    return True


# ── MAIN ──────────────────────────────────────────────────────
def main() -> None:
    """Descarga todos los GeoTIFFs desde Drive a data/raw/."""
    print("=" * 60)
    print("DESCARGA ÚNICA — GeoTIFFs desde Google Drive")
    print("=" * 60)

    service = autenticar_drive()
    carpeta_id = buscar_carpeta(service, CONFIG["drive_folder"])
    if not carpeta_id:
        return

    print(f"\n[+] Carpeta '{CONFIG['drive_folder']}' encontrada en Drive.")
    print(f"[+] Destino local: {PATHS['sentinel_2015'].parent.absolute()}\n")

    exitosos = 0
    for nombre_archivo in CONFIG["drive_files"]:
        print(f"[→] {nombre_archivo}")
        archivo_id = buscar_archivo(service, nombre_archivo, carpeta_id)
        if archivo_id:
            destino = PATHS["sentinel_2015"].parent / nombre_archivo
            if descargar_archivo(service, archivo_id, destino):
                exitosos += 1
        print()

    print("=" * 60)
    print(f"[✓] Descarga completada: {exitosos}/{len(CONFIG['drive_files'])} archivos.")
    print("    Siguiente paso: python scripts/03_generar_dataset.py")
    print("=" * 60)


if __name__ == "__main__":
    main()