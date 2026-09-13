#!/usr/bin/env python3
"""
BMKG Real-Time Earthquake & Tsunami Guardian Daemon.
Monitors BMKG API every 45s, calculates distance to user's home & office,
and immediately pushes critical earthquake/tsunami alerts with Shakemap images to Telegram.
"""

import os
import sys
import time
import math
import json
import sqlite3
import logging
import urllib.request
import urllib.parse
from pathlib import Path

# Paths & Settings
BASE_DIR = Path("/home/arusuka/mcp-weather")
DB_PATH = BASE_DIR / "bmkg_alerts.db"
LOG_FILE = BASE_DIR / "guardian.log"

logging.basicConfig(
    filename=str(LOG_FILE),
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("bmkg_guardian")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

# User Target Locations (Surabaya - Home & Office)
LOCATIONS = [
    {"name": "Rumah & Kantor (Surabaya)", "lat": -7.2575, "lon": 112.7521}
]

def get_telegram_token() -> str:
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    if token:
        return token
    env_file = Path("/home/arusuka/.hermes/.env")
    if env_file.exists():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("TELEGRAM_BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    return ""

def get_active_chat_ids() -> list[str]:
    chat_ids = set()
    env_chat = os.environ.get("TELEGRAM_CHAT_ID", "").strip()
    if env_chat:
        chat_ids.add(env_chat)
    try:
        conn = sqlite3.connect("/home/arusuka/.hermes/state.db")
        cur = conn.cursor()
        rows = cur.execute("SELECT DISTINCT chat_id FROM delivery_obligations WHERE platform = 'telegram'").fetchall()
        for r in rows:
            if r[0]:
                chat_ids.add(str(r[0]))
    except Exception:
        pass
    return list(chat_ids)

def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c

def init_db():
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS seen_gempa (
                datetime_id TEXT PRIMARY KEY,
                magnitude REAL,
                wilayah TEXT,
                potensi TEXT,
                notified_at REAL
            )
        """)

def is_gempa_seen(datetime_id: str) -> bool:
    with sqlite3.connect(str(DB_PATH)) as conn:
        cur = conn.execute("SELECT 1 FROM seen_gempa WHERE datetime_id = ?", (datetime_id,))
        return cur.fetchone() is not None

def mark_gempa_seen(datetime_id: str, mag: float, wilayah: str, potensi: str):
    with sqlite3.connect(str(DB_PATH)) as conn:
        conn.execute(
            "INSERT OR REPLACE INTO seen_gempa (datetime_id, magnitude, wilayah, potensi, notified_at) VALUES (?, ?, ?, ?, ?)",
            (datetime_id, mag, wilayah, potensi, time.time())
        )

def send_telegram_alert(message: str, image_url: str = ""):
    token = get_telegram_token()
    chat_ids = get_active_chat_ids()

    for cid in chat_ids:
        try:
            if image_url:
                # Send photo with caption
                api_url = f"https://api.telegram.org/bot{token}/sendPhoto"
                payload = json.dumps({
                    "chat_id": cid,
                    "photo": image_url,
                    "caption": message,
                    "parse_mode": "Markdown"
                }).encode("utf-8")
            else:
                api_url = f"https://api.telegram.org/bot{token}/sendMessage"
                payload = json.dumps({
                    "chat_id": cid,
                    "text": message,
                    "parse_mode": "Markdown"
                }).encode("utf-8")

            req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                logger.info("Sent BMKG alert to %s: %s", cid, resp.status)
        except Exception as e:
            logger.error("Failed to send alert to %s: %s", cid, str(e))
            # Fallback to plain text if photo fails
            if image_url:
                try:
                    api_url = f"https://api.telegram.org/bot{token}/sendMessage"
                    payload = json.dumps({"chat_id": cid, "text": message, "parse_mode": "Markdown"}).encode("utf-8")
                    req = urllib.request.Request(api_url, data=payload, headers={"Content-Type": "application/json"})
                    urllib.request.urlopen(req, timeout=10)
                except Exception:
                    pass

def check_bmkg():
    url = "https://data.bmkg.go.id/DataMKG/TEWS/autogempa.json"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            gempa = data.get("Infogempa", {}).get("gempa", {})
            if not gempa:
                return

            dt_id = gempa.get("DateTime") or f"{gempa.get('Tanggal')}_{gempa.get('Jam')}"
            if is_gempa_seen(dt_id):
                return

            # Parse coordinates
            coords_str = gempa.get("Coordinates", "")
            if not coords_str or "," not in coords_str:
                return
            
            g_lat, g_lon = [float(x.strip()) for x in coords_str.split(",")]
            try:
                mag = float(gempa.get("Magnitude", 0))
            except ValueError:
                mag = 0.0

            wilayah = gempa.get("Wilayah", "")
            potensi = gempa.get("Potensi", "")
            dirasakan = gempa.get("Dirasakan", "")
            kedalaman = gempa.get("Kedalaman", "")
            waktu = f"{gempa.get('Tanggal')} • {gempa.get('Jam')}"
            shakemap_file = gempa.get("Shakemap", "")
            shakemap_url = f"https://data.bmkg.go.id/DataMKG/TEWS/{shakemap_file}" if shakemap_file else ""

            # Check distance to Surabaya
            user_loc = LOCATIONS[0]
            dist = haversine_km(user_loc["lat"], user_loc["lon"], g_lat, g_lon)

            # Determine relevance
            is_tsunami_threat = "tsunami" in potensi.lower() and "tidak berpotensi" not in potensi.lower()
            is_close = dist <= 350
            is_medium_felt = dist <= 750 and mag >= 5.0
            is_major = mag >= 6.5
            is_explicit_felt = any(k in (dirasakan + " " + wilayah).lower() for k in ["surabaya", "sidoarjo", "gresik", "jawa timur", "jatim", "malang"])

            should_alert = is_tsunami_threat or is_close or is_medium_felt or is_major or is_explicit_felt

            if should_alert:
                if is_tsunami_threat:
                    level_header = "🚨🔴 **PERINGATAN DINI TSUNAMI (BMKG)** 🔴🚨"
                    advice = "⚠️ **SEGERA EVAKUASI KE TEMPAT TINGGI!** Ikuti instruksi resmi BPBD & BMKG setempat."
                elif is_close and mag >= 5.0:
                    level_header = "⚠️🔴 **PERINGATAN GEMPA SIGNIFIKAN DEKAT LOKASI ANDA**"
                    advice = "Tetap tenang, jauhi kaca/bangunan retak, dan cari tempat perlindungan yang kokoh."
                elif is_close or is_explicit_felt:
                    level_header = "📢🟡 **INFO GEMPA DIRASAKAN (BMKG)**"
                    advice = "Gempa berpotensi terasa di sekitar lokasi Anda. Tetap waspada terhadap gempa susulan."
                else:
                    level_header = "ℹ️🔵 **INFO GEMPA BUMI BMKG (M ≥ 5.0)**"
                    advice = "Informasi resmi pemantauan gempa BMKG Indonesia."

                tsunami_status = "⚠️ **BERPOTENSI TSUNAMI**" if is_tsunami_threat else "✅ Tidak Berpotensi Tsunami"

                msg = f"""{level_header}

📍 **Pusat Gempa:** {wilayah}
📏 **Jarak ke Rumah & Kantor:** ±`{dist:.0f} km` dari Surabaya
💥 **Kekuatan:** **{mag} SR** (Kedalaman: {kedalaman})
⏰ **Waktu:** {waktu}
🌊 **Status Tsunami:** {tsunami_status}
📳 **Dampak Dirasakan:** {dirasakan or 'Dalam pemutakhiran'}

💡 **Pesan Arusuka:**
{advice}
"""
                send_telegram_alert(msg, shakemap_url)
                logger.info("Sent alert for earthquake %s (Mag %s, Dist %s km)", dt_id, mag, dist)

            mark_gempa_seen(dt_id, mag, wilayah, potensi)

    except Exception as e:
        logger.error("Error during BMKG check: %s", str(e))

def run_loop():
    init_db()
    logger.info("BMKG Real-Time Guardian started. Monitoring every 45s for Home & Office (Surabaya)...")
    while True:
        try:
            check_bmkg()
        except Exception as e:
            logger.error("Unexpected error in main loop: %s", str(e))
        time.sleep(45)

if __name__ == "__main__":
    if "--test" in sys.argv:
        init_db()
        print("Running one-off test check...")
        check_bmkg()
        print("Check completed.")
    else:
        run_loop()
