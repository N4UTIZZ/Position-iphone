#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Outil local : simuler la position GPS d'un iPhone depuis le PC."""

from __future__ import annotations

import base64
import hmac
import io
import json
import re
import secrets
import socket
import subprocess
import sys
import threading
import time
import webbrowser
from pathlib import Path
from typing import Any, Optional

import requests
from flask import Flask, g, jsonify, make_response, render_template, request, send_from_directory

HOST = "0.0.0.0"
PORT = 5000
TUNNELD_HOST = "127.0.0.1"
TUNNELD_PORT = 49151

NOMINATIM_SEARCH = "https://nominatim.openstreetmap.org/search"
NOMINATIM_REVERSE = "https://nominatim.openstreetmap.org/reverse"
NOMINATIM_HEADERS = {
    "User-Agent": "IPhoneLocationLocal/1.0 (local personal desktop tool)",
    "Accept-Language": "fr",
}
NOMINATIM_MIN_INTERVAL = 1.1

PARIS_LAT = 48.8566
PARIS_LON = 2.3522

APP_DIR = Path(__file__).resolve().parent
TOKEN_FILE = APP_DIR / "access_token.txt"
TOKEN_COOKIE = "iphone_location_token"

app = Flask(__name__, static_folder="static", template_folder="templates")

_nominatim_lock = threading.Lock()
_nominatim_last = 0.0
_device_lock = threading.Lock()
_set_proc: Optional[subprocess.Popen] = None
_set_proc_output: list[str] = []
_active: dict[str, Any] = {
    "active": False,
    "lat": None,
    "lon": None,
    "label": None,
    "ios": None,
}


def load_or_create_token() -> str:
    try:
        if TOKEN_FILE.is_file():
            tok = TOKEN_FILE.read_text(encoding="utf-8").strip()
            if tok:
                return tok
    except OSError:
        pass
    tok = secrets.token_urlsafe(16)
    try:
        TOKEN_FILE.write_text(tok + "\n", encoding="utf-8")
        try:
            TOKEN_FILE.chmod(0o600)
        except OSError:
            pass
    except OSError as exc:
        print(f"[ATTENTION] Impossible d'enregistrer le code secret : {exc}", flush=True)
    return tok


def get_token() -> str:
    tok = app.config.get("ACCESS_TOKEN")
    if tok:
        return str(tok)
    tok = load_or_create_token()
    app.config["ACCESS_TOKEN"] = tok
    return tok


def lan_ips() -> list[str]:
    found: list[str] = []

    def add(ip: str) -> None:
        if not ip or ip.startswith("127.") or ip.startswith("0."):
            return
        if ip.startswith("169.254."):
            return
        if ip not in found:
            found.append(ip)

    try:
        probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        probe.settimeout(0.4)
        probe.connect(("8.8.8.8", 80))
        add(probe.getsockname()[0])
        probe.close()
    except OSError:
        pass

    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            add(info[4][0])
    except OSError:
        pass

    try:
        import psutil  # type: ignore

        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                if getattr(addr, "family", None) == socket.AF_INET:
                    add(addr.address)
    except Exception:
        pass

    return found


def qr_data_uri(url: str) -> str:
    import qrcode

    img = qrcode.make(url)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode("ascii")


def print_qr_terminal(url: str) -> None:
    import qrcode

    qr = qrcode.QRCode(border=1)
    qr.add_data(url)
    qr.make(fit=True)
    qr.print_ascii(out=sys.stdout, invert=True)
    sys.stdout.flush()


def extract_token() -> str:
    raw = request.args.get("t") or request.cookies.get(TOKEN_COOKIE) or ""
    if not raw:
        header = request.headers.get("X-Access-Token") or request.headers.get("Authorization") or ""
        if header.lower().startswith("bearer "):
            raw = header[7:]
        elif header:
            raw = header
    return raw.strip()


def token_is_valid(candidate: str) -> bool:
    expected = get_token()
    if not candidate or not expected:
        return False
    a = candidate.encode("utf-8")
    b = expected.encode("utf-8")
    if len(a) != len(b):
        return False
    return hmac.compare_digest(a, b)


def wants_json() -> bool:
    if request.path.startswith("/api/"):
        return True
    accept = (request.headers.get("Accept") or "").lower()
    return "application/json" in accept and "text/html" not in accept


@app.before_request
def require_token():
    if request.method == "OPTIONS":
        return ("", 204)
    if request.path in {"/favicon.ico", "/sw.js", "/manifest.webmanifest"} or request.path.startswith("/static/"):
        return None
    if token_is_valid(extract_token()):
        g.auth_ok = True
        return None
    g.auth_ok = False
    if wants_json():
        return jsonify(
            {
                "ok": False,
                "error": "Accès refusé. Ouvre le lien complet affiché sur le PC (avec le code), ou scanne le QR code.",
            }
        ), 403
    resp = make_response(render_template("locked.html"), 403)
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.after_request
def set_auth_cookie(resp):
    if getattr(g, "auth_ok", False):
        resp.set_cookie(
            TOKEN_COOKIE,
            get_token(),
            max_age=60 * 60 * 24 * 30,
            httponly=True,
            samesite="Lax",
            path="/",
        )
        resp.headers["Cache-Control"] = "no-store"
    return resp


class DeviceError(Exception):
    """Erreur parlante, déjà rédigée en français."""


def _throttle_nominatim() -> None:
    global _nominatim_last
    with _nominatim_lock:
        wait = NOMINATIM_MIN_INTERVAL - (time.monotonic() - _nominatim_last)
        if wait > 0:
            time.sleep(wait)
        _nominatim_last = time.monotonic()


def geocode_address(query: str, limit: int = 5) -> list[dict[str, Any]]:
    query = (query or "").strip()
    if not query:
        return []
    _throttle_nominatim()
    resp = requests.get(
        NOMINATIM_SEARCH,
        params={
            "q": query,
            "format": "jsonv2",
            "limit": limit,
            "addressdetails": 1,
        },
        headers=NOMINATIM_HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    results = []
    for item in resp.json() or []:
        try:
            results.append(
                {
                    "label": item.get("display_name") or query,
                    "lat": float(item["lat"]),
                    "lon": float(item["lon"]),
                    "type": item.get("type") or item.get("addresstype") or "",
                }
            )
        except (KeyError, TypeError, ValueError):
            continue
    return results


def reverse_geocode(lat: float, lon: float) -> str:
    _throttle_nominatim()
    resp = requests.get(
        NOMINATIM_REVERSE,
        params={
            "lat": lat,
            "lon": lon,
            "format": "jsonv2",
            "addressdetails": 1,
        },
        headers=NOMINATIM_HEADERS,
        timeout=20,
    )
    resp.raise_for_status()
    data = resp.json() or {}
    return data.get("display_name") or f"{lat:.6f}, {lon:.6f}"


def tunneld_disponible() -> bool:
    try:
        with socket.create_connection((TUNNELD_HOST, TUNNELD_PORT), timeout=0.4):
            return True
    except OSError:
        return False


def _popen_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.DEVNULL,
        "text": True,
        "encoding": "utf-8",
        "errors": "replace",
    }
    if sys.platform == "win32":
        kwargs["creationflags"] = (
            subprocess.CREATE_NEW_PROCESS_GROUP | getattr(subprocess, "CREATE_NO_WINDOW", 0)
        )
    else:
        kwargs["start_new_session"] = True
    return kwargs


def run_pmd(args: list[str], timeout: int = 60) -> subprocess.CompletedProcess:
    cmd = [sys.executable, "-m", "pymobiledevice3", *args]
    try:
        return subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
    except FileNotFoundError as exc:
        raise DeviceError(
            "Python est introuvable. Réinstalle Python 3.11+ en cochant "
            "« Add python.exe to PATH », puis relance start.bat."
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise DeviceError(
            "La commande vers l'iPhone a mis trop de temps à répondre. "
            "Vérifie que le téléphone est déverrouillé et bien branché, puis réessaie."
        ) from exc


def _combined_output(proc: subprocess.CompletedProcess) -> str:
    return ((proc.stdout or "") + "\n" + (proc.stderr or "")).strip()


def traduit_erreur(output: str, returncode: int | None = None) -> str:
    text = output or ""
    low = text.lower()

    if "modulenotfounderror" in low or "no module named 'pymobiledevice3'" in low:
        return (
            "pymobiledevice3 n'est pas installé. Ferme cette page, "
            "relance start.bat et attends la fin de l'installation."
        )
    if "devicenotconnected" in low or "no device connected" in low or "device is not connected" in low:
        return (
            "Aucun iPhone n'est détecté. Branche-le avec un câble USB de données, "
            "déverrouille-le et accepte « Approuver cet ordinateur »."
        )
    if "usbmuxd" in low or "failed to connect to usbmux" in low or "apple mobile device" in low:
        return (
            "Aucun iPhone n'est détecté, ou les pilotes Apple ne sont pas installés. "
            "Installe iTunes pour Windows (version classique), branche l'iPhone avec un câble USB de données, "
            "déverrouille-le et accepte « Approuver cet ordinateur »."
        )
    if "notpaired" in low or "pairing" in low and "dialog" in low:
        return (
            "L'iPhone n'a pas encore approuvé cet ordinateur. "
            "Déverrouille-le et appuie sur « Approuver » dans la fenêtre qui s'affiche."
        )
    if "passwordrequired" in low or "device is locked" in low or "locked" in low and "unlock" in low:
        return "L'iPhone est verrouillé. Déverrouille-le et réessaie."
    if "tunneldconnectionerror" in low or "unable to connect to tunneld" in low:
        return (
            "Impossible de joindre le tunnel (tunneld). Sur iOS 17.0 à 17.3, "
            "relance start.bat et accepte la demande d'administrateur Windows. "
            "Laisse ensuite la fenêtre tunneld ouverte."
        )
    if "invalidserviceerror" in low or "failed to start service" in low:
        return (
            "Impossible de démarrer le service développeur. Active le Mode développeur "
            "(Réglages → Confidentialité et sécurité → Mode développeur). "
            "Sur iOS 16 ou moins, l'image disque développeur doit aussi être montée "
            "(l'outil essaie automatiquement, la première fois ça peut prendre plusieurs minutes)."
        )
    if "developermode" in low or "developer mode" in low:
        return (
            "Le Mode développeur n'est pas activé. Va dans Réglages → Confidentialité "
            "et sécurité → Mode développeur, active-le, laisse l'iPhone redémarrer et confirme. "
            "Si le menu est absent, lance dans le dossier de l'outil : "
            "python -m pymobiledevice3 amfi reveal-developer-mode"
        )
    if "devicehaspasscodeset" in low or "passcode set" in low:
        return (
            "L'iPhone a un code : le Mode développeur doit être activé à la main "
            "dans Réglages → Confidentialité et sécurité → Mode développeur."
        )
    if "already mounted" in low:
        return ""
    if returncode not in (0, None) and text:
        extrait = text.strip()
        if len(extrait) > 800:
            extrait = extrait[:800] + "…"
        return f"La commande vers l'iPhone a échoué :\n{extrait}"
    if returncode not in (0, None):
        return (
            "La commande vers l'iPhone a échoué. Vérifie le câble, le Mode développeur "
            "et que start.bat a bien fini d'installer les dépendances."
        )
    return ""


def lister_appareils() -> list[dict[str, Any]]:
    proc = run_pmd(["usbmux", "list"], timeout=25)
    out = _combined_output(proc)
    if proc.returncode != 0:
        msg = traduit_erreur(out, proc.returncode)
        raise DeviceError(msg or "Impossible de lister les iPhone connectés.")

    raw = out.strip()
    if not raw or raw in ("[]", "{}", "null"):
        return []

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise DeviceError(
            "La liste des appareils n'a pas pu être lue. "
            "Vérifie que pymobiledevice3 est bien installé (relance start.bat)."
        ) from exc

    devices: list[dict[str, Any]] = []
    if isinstance(data, dict):
        # Soit un seul appareil à plat, soit un dictionnaire indexé par UDID.
        if "ProductVersion" in data or "DeviceName" in data or "Identifier" in data:
            items = [data]
        else:
            items = list(data.values())
    elif isinstance(data, list):
        items = data
    else:
        items = []

    for item in items:
        if not isinstance(item, dict):
            continue
        udid = (
            item.get("Identifier")
            or item.get("UniqueDeviceID")
            or item.get("SerialNumber")
            or item.get("udid")
            or ""
        )
        devices.append(
            {
                "udid": str(udid),
                "name": item.get("DeviceName") or item.get("MarketName") or "iPhone",
                "version": str(item.get("ProductVersion") or item.get("OSVersion") or ""),
                "product": item.get("ProductType") or "",
                "connection": item.get("ConnectionType") or item.get("connectionType") or "",
            }
        )
    return devices


def choisir_appareil() -> dict[str, Any]:
    devices = lister_appareils()
    if not devices:
        raise DeviceError(
            "Aucun iPhone n'est détecté. Branche-le avec un câble USB de données, "
            "déverrouille-le et accepte « Approuver cet ordinateur »."
        )
    usb = [d for d in devices if str(d.get("connection", "")).upper() == "USB"]
    return usb[0] if usb else devices[0]


def version_majeure(version: str) -> Optional[int]:
    if not version:
        return None
    m = re.match(r"(\d+)", str(version).strip())
    return int(m.group(1)) if m else None


def completer_version(device: dict[str, Any]) -> dict[str, Any]:
    if device.get("version"):
        return device
    args = ["lockdown", "info"]
    if device.get("udid"):
        args.extend(["--udid", device["udid"]])
    proc = run_pmd(args, timeout=30)
    out = _combined_output(proc)
    if proc.returncode != 0:
        msg = traduit_erreur(out, proc.returncode)
        if msg:
            raise DeviceError(msg)
        return device
    # Sortie JSON ou texte "ProductVersion: 17.6.1"
    version = ""
    try:
        data = json.loads(out)
        if isinstance(data, dict):
            version = str(data.get("ProductVersion") or "")
    except json.JSONDecodeError:
        m = re.search(r"ProductVersion['\"]?\s*[:=]\s*['\"]?([0-9.]+)", out)
        if m:
            version = m.group(1)
    if version:
        device = dict(device)
        device["version"] = version
    return device


def est_ios17_plus(device: dict[str, Any]) -> bool:
    major = version_majeure(device.get("version") or "")
    if major is None:
        # En cas de doute, on tente l'API iOS 17+ (la plus courante aujourd'hui).
        return True
    return major >= 17


def monter_developer_disk(device: dict[str, Any]) -> None:
    args = ["mounter", "auto-mount"]
    if device.get("udid"):
        args.extend(["--udid", device["udid"]])
    proc = run_pmd(args, timeout=240)
    out = _combined_output(proc)
    if proc.returncode != 0:
        low = out.lower()
        if "already mounted" in low:
            return
        msg = traduit_erreur(out, proc.returncode)
        raise DeviceError(
            msg
            or (
                "Impossible de monter l'image disque développeur (nécessaire sur iOS 16 ou moins, "
                "à refaire après chaque redémarrage de l'iPhone). Vérifie Internet et le Mode développeur."
            )
        )


def _flags_connexion(device: dict[str, Any], ios17: bool) -> list[str]:
    flags: list[str] = []
    if device.get("udid"):
        flags.extend(["--udid", device["udid"]])
    if ios17 and tunneld_disponible():
        # UDID explicite pour éviter un choix interactif si --tunnel est vide.
        flags.extend(["--tunnel", device.get("udid") or ""])
    return flags


def _arreter_processus_set() -> None:
    global _set_proc, _set_proc_output
    proc = _set_proc
    _set_proc = None
    if proc is None or proc.poll() is not None:
        return
    try:
        if sys.platform == "win32":
            try:
                proc.send_signal(subprocess.CTRL_BREAK_EVENT)  # type: ignore[attr-defined]
            except (ProcessLookupError, OSError, AttributeError):
                proc.terminate()
        else:
            proc.terminate()
        try:
            proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    _set_proc_output = []


def _lire_sortie(proc: subprocess.Popen, buffer: list[str]) -> None:
    try:
        if proc.stdout is None:
            return
        for line in proc.stdout:
            buffer.append(line)
            if len(buffer) > 400:
                del buffer[:200]
    except Exception:
        return


def appliquer_position(lat: float, lon: float, label: str) -> dict[str, Any]:
    global _set_proc, _set_proc_output, _active

    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        raise DeviceError("Les coordonnées sont invalides.")

    with _device_lock:
        _arreter_processus_set()
        device = completer_version(choisir_appareil())
        ios17 = est_ios17_plus(device)
        flags = _flags_connexion(device, ios17)

        if ios17:
            cmd = [
                sys.executable,
                "-m",
                "pymobiledevice3",
                "developer",
                "dvt",
                "simulate-location",
                "set",
                *flags,
                "--",
                f"{lat:.8f}",
                f"{lon:.8f}",
            ]
            buffer: list[str] = []
            try:
                proc = subprocess.Popen(cmd, **_popen_kwargs())
            except FileNotFoundError as exc:
                raise DeviceError(
                    "Python est introuvable. Réinstalle Python 3.11+ en cochant "
                    "« Add python.exe to PATH », puis relance start.bat."
                ) from exc

            _set_proc = proc
            _set_proc_output = buffer
            threading.Thread(target=_lire_sortie, args=(proc, buffer), daemon=True).start()

            started = time.monotonic()
            deadline = started + 45
            while time.monotonic() < deadline:
                chunk = "".join(buffer)
                if proc.poll() is not None:
                    msg = traduit_erreur(chunk, proc.returncode)
                    _set_proc = None
                    raise DeviceError(
                        msg
                        or (
                            "La simulation s'est arrêtée tout de suite. "
                            "Vérifie le Mode développeur, le câble, et (iOS 17.0–17.3) que tunneld tourne en administrateur."
                        )
                    )
                low = chunk.lower()
                if "press ctrl+c" in low or "sigint" in low:
                    break
                # Toujours en cours après 6 s : on considère que la session tient.
                if time.monotonic() - started >= 6 and "error" not in low and "traceback" not in low:
                    break
                time.sleep(0.25)

            if proc.poll() is not None:
                msg = traduit_erreur("".join(buffer), proc.returncode)
                _set_proc = None
                raise DeviceError(msg or "La simulation s'est arrêtée tout de suite.")

            _active = {
                "active": True,
                "lat": lat,
                "lon": lon,
                "label": label,
                "ios": device.get("version") or "17+",
            }
            return {
                "ok": True,
                "message": (
                    f"Position appliquée ({lat:.5f}, {lon:.5f}). "
                    "Laisse start.bat et cette page ouverts, et l'iPhone branché, "
                    "sinon la simulation s'arrête (iOS 17+)."
                ),
                "device": {
                    "name": device.get("name"),
                    "version": device.get("version"),
                    "udid": device.get("udid"),
                },
                "tunneld": tunneld_disponible(),
            }

        # iOS 16 et moins : la position reste jusqu'à clear / redémarrage.
        monter_developer_disk(device)
        args = [
            "developer",
            "simulate-location",
            "set",
            *flags,
            "--",
            f"{lat:.8f}",
            f"{lon:.8f}",
        ]
        proc = run_pmd(args, timeout=90)
        out = _combined_output(proc)
        if proc.returncode != 0:
            msg = traduit_erreur(out, proc.returncode)
            raise DeviceError(msg or "Impossible d'appliquer la position sur l'iPhone.")

        _active = {
            "active": True,
            "lat": lat,
            "lon": lon,
            "label": label,
            "ios": device.get("version") or "16-",
        }
        return {
            "ok": True,
            "message": (
                f"Position appliquée ({lat:.5f}, {lon:.5f}). "
                "Sur iOS 16 ou moins, elle reste jusqu'à « Réinitialiser » ou un redémarrage de l'iPhone."
            ),
            "device": {
                "name": device.get("name"),
                "version": device.get("version"),
                "udid": device.get("udid"),
            },
            "tunneld": tunneld_disponible(),
        }


def reinitialiser_position() -> dict[str, Any]:
    global _active
    with _device_lock:
        _arreter_processus_set()
        device = None
        ios17 = True
        try:
            device = completer_version(choisir_appareil())
            ios17 = est_ios17_plus(device)
        except DeviceError as exc:
            # Même sans appareil, on a déjà tué le processus set (iOS 17+).
            _active = {"active": False, "lat": None, "lon": None, "label": None, "ios": None}
            return {
                "ok": True,
                "message": (
                    "La simulation locale a été arrêtée. "
                    "Aucun iPhone n'est détecté pour envoyer la commande « clear » : "
                    f"{exc}"
                ),
            }

        flags = _flags_connexion(device, ios17)
        if ios17:
            args = ["developer", "dvt", "simulate-location", "clear", *flags]
        else:
            try:
                monter_developer_disk(device)
            except DeviceError:
                pass
            args = ["developer", "simulate-location", "clear", *flags]

        proc = run_pmd(args, timeout=60)
        out = _combined_output(proc)
        _active = {"active": False, "lat": None, "lon": None, "label": None, "ios": device.get("version")}
        if proc.returncode != 0:
            msg = traduit_erreur(out, proc.returncode)
            # Arrêter le process set a souvent déjà suffi sur iOS 17+.
            return {
                "ok": True,
                "message": (
                    "La simulation a été arrêtée côté PC. "
                    "La commande « clear » a cependant renvoyé une erreur"
                    + (f" : {msg}" if msg else ".")
                    + " Si la fausse position reste affichée, redémarre l'iPhone."
                ),
                "device": {
                    "name": device.get("name"),
                    "version": device.get("version"),
                    "udid": device.get("udid"),
                },
            }

        return {
            "ok": True,
            "message": (
                "Position réelle rétablie. Les applis peuvent mettre quelques instants à se mettre à jour. "
                "Si ça reste bloqué, applique d'abord une adresse proche de ta vraie position, "
                "puis réinitialise, ou redémarre l'iPhone."
            ),
            "device": {
                "name": device.get("name"),
                "version": device.get("version"),
                "udid": device.get("udid"),
            },
        }


def statut() -> dict[str, Any]:
    info: dict[str, Any] = {
        "ok": True,
        "tunneld": tunneld_disponible(),
        "simulation": dict(_active),
        "device": None,
        "error": None,
    }
    # Si le processus iOS 17+ est mort, la simulation n'est plus active.
    if _set_proc is not None and _set_proc.poll() is not None:
        with _device_lock:
            if _set_proc is not None and _set_proc.poll() is not None:
                _active.update({"active": False})
                info["simulation"] = dict(_active)
    try:
        device = completer_version(choisir_appareil())
        info["device"] = {
            "name": device.get("name"),
            "version": device.get("version"),
            "udid": device.get("udid"),
            "product": device.get("product"),
            "connection": device.get("connection"),
            "ios17": est_ios17_plus(device),
        }
    except DeviceError as exc:
        info["device"] = None
        info["error"] = str(exc)
    return info



# ---------- Routes HTTP ----------

@app.get("/")
def accueil():
    return render_template(
        "page.html",
        paris_lat=PARIS_LAT,
        paris_lon=PARIS_LON,
        phone_url=app.config.get("PHONE_URL") or "",
        phone_urls=app.config.get("PHONE_URLS") or [],
        qr_data_uri=app.config.get("QR_DATA_URI") or "",
    )


@app.get("/favicon.ico")
def favicon():
    icone = Path(app.static_folder) / "apple-touch-icon.png"
    if icone.is_file():
        return send_from_directory(app.static_folder, "apple-touch-icon.png", mimetype="image/png")
    return send_from_directory(app.static_folder, "icone.svg", mimetype="image/svg+xml")


@app.get("/sw.js")
def service_worker():
    resp = send_from_directory(app.static_folder, "sw.js", mimetype="application/javascript")
    resp.headers["Service-Worker-Allowed"] = "/"
    resp.headers["Cache-Control"] = "no-cache"
    return resp


@app.get("/manifest.webmanifest")
def manifest():
    start_url = "/"
    # Uniquement si la requête est déjà authentifiée (cookie ou ?t=) : ne pas publier le jeton au LAN.
    candidate = extract_token()
    if token_is_valid(candidate):
        start_url = f"/?t={get_token()}"
        g.auth_ok = True
    data = {
        "name": "Position",
        "short_name": "Position",
        "lang": "fr",
        "start_url": start_url,
        "scope": "/",
        "display": "standalone",
        "background_color": "#14170f",
        "theme_color": "#14170f",
        "icons": [
            {"src": "/static/icone.svg", "sizes": "any", "type": "image/svg+xml", "purpose": "any"},
            {"src": "/static/icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any"},
            {"src": "/static/icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any"},
        ],
    }
    resp = jsonify(data)
    resp.mimetype = "application/manifest+json"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.get("/api/status")
def api_status():
    return jsonify(statut())


@app.get("/api/geocode")
def api_geocode():
    q = request.args.get("q", "")
    if not q.strip():
        return jsonify({"ok": False, "error": "Tape une adresse à rechercher."}), 400
    try:
        results = geocode_address(q)
    except requests.RequestException:
        return jsonify(
            {
                "ok": False,
                "error": "La recherche d'adresse a échoué (OpenStreetMap). Vérifie Internet et réessaie.",
            }
        ), 502
    if not results:
        return jsonify({"ok": False, "error": "Aucun résultat pour cette adresse. Essaie d'être plus précis.", "results": []})
    return jsonify({"ok": True, "results": results})


@app.get("/api/reverse")
def api_reverse():
    try:
        lat = float(request.args.get("lat", ""))
        lon = float(request.args.get("lon", ""))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Coordonnées invalides."}), 400
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return jsonify({"ok": False, "error": "Coordonnées invalides."}), 400
    try:
        label = reverse_geocode(lat, lon)
    except requests.RequestException:
        label = f"{lat:.6f}, {lon:.6f}"
    return jsonify({"ok": True, "label": label, "lat": lat, "lon": lon})


@app.post("/api/apply")
def api_apply():
    data = request.get_json(silent=True) or {}
    try:
        lat = float(data.get("lat"))
        lon = float(data.get("lon"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "Choisis d'abord un point sur la carte ou recherche une adresse."}), 400
    label = str(data.get("label") or f"{lat:.6f}, {lon:.6f}")
    try:
        result = appliquer_position(lat, lon, label)
        return jsonify(result)
    except DeviceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


@app.post("/api/reset")
def api_reset():
    try:
        result = reinitialiser_position()
        return jsonify(result)
    except DeviceError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400


def main() -> None:
    token = get_token()
    urls = [f"http://{ip}:{PORT}/?t={token}" for ip in lan_ips()]
    local = f"http://127.0.0.1:{PORT}/?t={token}"
    primary = urls[0] if urls else local
    app.config["ACCESS_TOKEN"] = token
    app.config["PHONE_URL"] = primary
    app.config["PHONE_URLS"] = urls
    try:
        app.config["QR_DATA_URI"] = qr_data_uri(primary)
    except Exception as exc:
        app.config["QR_DATA_URI"] = ""
        print(f"[ATTENTION] QR code image indisponible : {exc}", flush=True)

    print("", flush=True)
    print("============================================", flush=True)
    print("  Position iPhone — interface prête", flush=True)
    print("============================================", flush=True)
    print("", flush=True)
    print(f"Sur ce PC :     {local}", flush=True)
    if urls:
        print("Depuis l'iPhone (même Wi-Fi que le PC) :", flush=True)
        for u in urls:
            print(f"  {u}", flush=True)
        print("", flush=True)
        print("Scanne ce QR code avec l'appareil photo de l'iPhone :", flush=True)
        print("", flush=True)
        try:
            print_qr_terminal(primary)
        except Exception as exc:
            print(f"(QR texte indisponible : {exc})", flush=True)
            print("Ouvre le lien ci-dessus, ou le QR affiché sur la page du PC.", flush=True)
    else:
        print("Aucune adresse Wi-Fi / réseau local n'a été trouvée.", flush=True)
        print("Connecte le PC au Wi-Fi (réseau Privé), puis relance start.bat.", flush=True)
    print("", flush=True)
    print("Le Wi-Fi du PC doit être en réseau « Privé », et le pare-feu", flush=True)
    print("doit autoriser le port 5000 (start.bat le demande en administrateur).", flush=True)
    print("Laisse cette fenêtre ouverte pendant la simulation (iOS 17+).", flush=True)
    print("Ne partage pas le lien : il contient le code d'accès.", flush=True)
    print("", flush=True)

    if sys.platform == "win32":
        def _open() -> None:
            time.sleep(1.0)
            try:
                webbrowser.open(local)
            except Exception:
                pass

        threading.Thread(target=_open, daemon=True).start()

    app.run(host=HOST, port=PORT, debug=False, threaded=True, use_reloader=False)


if __name__ == "__main__":
    main()
