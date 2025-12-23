#!/usr/bin/env python3
"""
MHFZ Patch Server Deploy Script - Versione Migliorata
Crea pacchetti ZIP deploy per Linux e Windows.
"""

import sys
import os
from pathlib import Path
from shutil import copy2, copytree, rmtree
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).parent
RELEASE_DIR = ROOT / "releases"
WIN_DIR = RELEASE_DIR / "Windows" / "patchserver"
LINUX_DIR = RELEASE_DIR / "Linux" / "patchserver"

def log(message: str, level: str = "INFO"):
    """Logging colorato per terminale"""
    colors = {"INFO": "\033[92m", "WARN": "\033[93m", "ERROR": "\033[91m", "SUCCESS": "\033[92m"}
    print(f"{colors.get(level, '')}{level}: {message}\033[0m")

def clean_dir(path: Path):
    """Pulisce e ricrea directory"""
    if path.exists():
        log(f"Pulizia directory: {path}", "INFO")
        rmtree(path)
    path.mkdir(parents=True, exist_ok=True)
    log(f"Creata directory: {path}", "SUCCESS")

def validate_files():
    """Valida prerequisiti"""
    required_common = ["game", "images", "launcher.json", "patch_config.json"]
    missing = []

    for item in required_common:
        if not (ROOT / item).exists():
            missing.append(item)

    if missing:
        log(f"MANCANO file: {', '.join(missing)}", "ERROR")
        return False

    log("Tutti i file comuni presenti ✓", "SUCCESS")
    return True

def prepare_common(target: Path):
    """Copia file comuni (game/, images/, JSON)"""
    log("Copia file comuni...", "INFO")
    copytree(ROOT / "game", target / "game", dirs_exist_ok=True)
    copytree(ROOT / "images", target / "images", dirs_exist_ok=True)
    copy2(ROOT / "launcher.json", target / "launcher.json")
    copy2(ROOT / "patch_config.json", target / "patch_config.json")
    log("File comuni copiati ✓", "SUCCESS")

def make_zip(src: Path, zip_path: Path):
    """Crea archivio ZIP"""
    log(f"Creazione ZIP: {zip_path}", "INFO")
    with ZipFile(zip_path, "w", ZIP_DEFLATED) as z:
        for path in src.rglob("*"):
            if path.is_file():
                arcname = path.relative_to(src.parent)
                z.write(path, arcname)
                log(f"Aggiunto: {arcname}", "INFO")
    log(f"ZIP creato: {zip_path} ({zip_path.stat().st_size / 1024:.1f} KB)", "SUCCESS")

def build_linux():
    """Build Linux (amd64)"""
    patchserver = ROOT / "patchserver"
    if not patchserver.exists():
        log("patchserver (Linux) non trovato, salto build Linux", "WARN")
        return False

    if not os.access(patchserver, os.X_OK):
        log("Rendo patchserver eseguibile...", "INFO")
        os.chmod(patchserver, 0o755)

    clean_dir(LINUX_DIR)
    prepare_common(LINUX_DIR)
    copy2(patchserver, LINUX_DIR / "patchserver")
    make_zip(LINUX_DIR, RELEASE_DIR / "Linux-amd64.zip")
    return True

def build_windows():
    """Build Windows"""
    patchserver_exe = ROOT / "patchserver.exe"
    if not patchserver_exe.exists():
        log("patchserver.exe (Windows) non trovato, salto build Windows", "WARN")
        return False

    clean_dir(WIN_DIR)
    prepare_common(WIN_DIR)
    copy2(patchserver_exe, WIN_DIR / "patchserver.exe")
    make_zip(WIN_DIR, RELEASE_DIR / "Windows-amd64.zip")
    return True

def main():
    """Funzione principale"""
    log("🚀 Inizio Deploy MHFZ Patch Server", "SUCCESS")

    # Validazione
    if not validate_files():
        sys.exit(1)

    # Crea releases/
    RELEASE_DIR.mkdir(exist_ok=True)

    # Build Linux
    linux_built = build_linux()

    # Build Windows
    windows_built = build_windows()

    # Risultati
    log("📦 Deploy completato!", "SUCCESS")
    if linux_built:
        log(f"✅ Linux-amd64.zip: {RELEASE_DIR / 'Linux-amd64.zip'}", "SUCCESS")
    if windows_built:
        log(f"✅ Windows-amd64.zip: {RELEASE_DIR / 'Windows-amd64.zip'}", "SUCCESS")

    log(f"📁 Directory releases: {RELEASE_DIR}", "INFO")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("Interrotto dall'utente", "WARN")
        sys.exit(1)
    except Exception as e:
        log(f"Errore critico: {e}", "ERROR")
        sys.exit(1)
