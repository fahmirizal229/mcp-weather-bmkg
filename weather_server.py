#!/usr/bin/env python3
"""
BMKG & Air Quality MCP Server.
Provides real-time hyper-local weather, Air Quality Index (AQI/PM2.5),
and BMKG earthquake alerts for Antigravity and Hermes Agent.
"""

import sys
import os
import json
import logging
from pathlib import Path

WEATHER_DIR = Path(__file__).parent.resolve()
sys.path.insert(0, str(WEATHER_DIR))

import weather_api

LOG_FILE = "/home/arusuka/mcp-weather/weather_server.log"
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
logger = logging.getLogger("weather_mcp")

TOOLS = [
    {
        "name": "weather_get_by_coordinates",
        "description": "Get hyper-local real-time weather and Air Quality Index (AQI, PM2.5, health advice) from exact GPS latitude and longitude (e.g. from user's live Telegram location).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "latitude": {"type": "number", "description": "GPS Latitude (e.g. -6.2088)."},
                "longitude": {"type": "number", "description": "GPS Longitude (e.g. 106.8456)."},
                "location_name": {"type": "string", "description": "Optional custom name for location."}
            },
            "required": ["latitude", "longitude"]
        }
    },
    {
        "name": "weather_get_by_city",
        "description": "Get current weather, daily forecast, and Air Quality Index (AQI/PM2.5) for any city or region in Indonesia or worldwide.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "city_name": {"type": "string", "description": "Name of the city/district (e.g. 'Bandung', 'Jakarta Selatan', 'Surabaya', 'Denpasar')."}
            },
            "required": ["city_name"]
        }
    },
    {
        "name": "weather_get_earthquake_bmkg",
        "description": "Get latest real-time earthquake data from BMKG Indonesia (Magnitude, Epicenter, Depth, Tsunami Potential, and Shakemap image).",
        "inputSchema": {
            "type": "object",
            "properties": {}
        }
    },
    {
        "name": "weather_save_default_location",
        "description": "Save user's home or preferred location to Second Brain so weather can be fetched automatically without asking for location.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "location_name": {"type": "string", "description": "Display name of the location (e.g. 'Jakarta Selatan', 'BSD City')."},
                "latitude": {"type": "number", "description": "GPS Latitude."},
                "longitude": {"type": "number", "description": "GPS Longitude."}
            },
            "required": ["location_name", "latitude", "longitude"]
        }
    }
]

def format_weather_report(data: dict) -> str:
    loc = data["location"]
    w = data["weather"]
    aq = data["air_quality"]
    
    return f"""### 🌤️ Laporan Cuaca & Kualitas Udara: {loc}

**🌡️ Kondisi Cuaca Saat Ini:**
- **Kondisi:** {w['icon']} {w['condition']}
- **Suhu:** {w['temperature_c']}°C *(Terasa seperti {w['feels_like_c']}°C)*
- **Suhu Harian:** Min {w['temp_min_c']}°C / Max {w['temp_max_c']}°C
- **Kelembapan:** {w['humidity_percent']}% | **Kecepatan Angin:** {w['wind_speed_kmh']} km/jam
- **Peluang Hujan Hari Ini:** {w['rain_probability_percent']}%

**🍃 Kualitas Udara (Air Quality):**
- **Indeks AQI (US):** `{aq['us_aqi']}` ({aq['icon']} **{aq['category']}**)
- **Partikel PM2.5:** `{aq['pm2_5']} µg/m³` | **PM10:** `{aq['pm10']} µg/m³`
- **Saran Kesehatan:** {aq['health_advice']}
"""

def handle_tool_call(name: str, args: dict) -> str:
    logger.info("Tool called: %s with args: %s", name, args)

    if name == "weather_get_by_coordinates":
        lat = float(args["latitude"])
        lon = float(args["longitude"])
        loc_name = args.get("location_name", "")
        data = weather_api.fetch_weather_and_aqi(lat, lon, loc_name)
        return format_weather_report(data)

    elif name == "weather_get_by_city":
        city = args["city_name"]
        geo = weather_api.geocode_city(city)
        if not geo:
            return f"Tidak dapat menemukan koordinat untuk kota '{city}'. Silakan periksa kembali ejaannya."
        lat, lon, display_name = geo
        data = weather_api.fetch_weather_and_aqi(lat, lon, display_name)
        return format_weather_report(data)

    elif name == "weather_get_earthquake_bmkg":
        g = weather_api.fetch_latest_earthquake()
        recent = weather_api.fetch_recent_earthquakes(limit=5)
        map_line = f"\n- **Peta Guncangan (Shakemap):** {g['shakemap_url']}" if g['shakemap_url'] else ""
        dist_line = f"\n- **Estimasi Jarak ke Surabaya:** **{g['distance_to_surabaya_km']} km**" if g.get('distance_to_surabaya_km') is not None else ""

        recent_rows = []
        for idx, item in enumerate(recent, 1):
            dist_str = f"{item['distance_to_surabaya_km']} km" if item.get('distance_to_surabaya_km') is not None else "-"
            recent_rows.append(
                f"{idx}. **M {item['magnitude']}** ({item['tanggal']} {item['jam']}) - {item['wilayah']} "
                f"[Kedalaman: {item['kedalaman']}, Jarak ke SBY: {dist_str}]\n"
                f"   *Dirasakan / Keterangan:* {item['dirasakan'] or item['potensi'] or '-'}"
            )
        recent_text = "\n\n".join(recent_rows) if recent_rows else "Belum ada riwayat gempa dirasakan tambahan."

        return f"""### 🚨 Gempa Bumi Terkini (BMKG Indonesia)

- **Waktu Gempa:** {g['tanggal']} pukul {g['jam']}
- **Kekuatan (Magnitudo):** **{g['magnitude']} SR**
- **Kedalaman:** {g['kedalaman']}
- **Pusat Gempa:** {g['wilayah']}
- **Koordinat:** `{g['coordinates']}`{dist_line}
- **Potensi:** {g['potensi']}
- **Wilayah Dirasakan:** {g['dirasakan'] or 'Belum ada laporan dirasakan'}{map_line}

---
### 📋 5 Gempa Bumi Terbaru (BMKG Dirasakan / Terkini)
{recent_text}
"""

    elif name == "weather_save_default_location":
        loc_file = Path("/home/arusuka/second-brain/Preferences/user_location.md")
        content = f"""---
title: User Default Location
tags: ["location", "weather", "preference"]
updated: 2026-09-10
---

# Lokasi Default Pengguna
- **Nama Lokasi**: {args['location_name']}
- **Latitude**: {args['latitude']}
- **Longitude**: {args['longitude']}

Links: [[Preferences/workflow]], [[Rules/core_rules]]
"""
        loc_file.write_text(content.strip() + "\n", encoding="utf-8")
        try:
            import subprocess
            subprocess.run(["/usr/bin/python3", "/home/arusuka/second-brain/engine/sync.py"], capture_output=True)
        except Exception:
            pass
        return f"Berhasil menyimpan lokasi default '{args['location_name']}' ({args['latitude']}, {args['longitude']}) ke Second Brain."

    else:
        raise ValueError(f"Unknown tool: {name}")

def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line.strip())
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")
        params = req.get("params", {})

        if method == "initialize":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {
                        "name": "bmkg-weather-airquality-mcp",
                        "version": "1.0.0"
                    }
                }
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass

        elif method == "tools/list":
            resp = {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": TOOLS}
            }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            try:
                result_text = handle_tool_call(tool_name, tool_args)
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": result_text}],
                        "isError": False
                    }
                }
            except Exception as err:
                logger.error("Error executing %s: %s", tool_name, str(err))
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [{"type": "text", "text": f"Error: {str(err)}"}],
                        "isError": True
                    }
                }
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        elif method == "ping":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": {}}
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()

        else:
            if req_id is not None:
                resp = {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "error": {"code": -32601, "message": f"Method '{method}' not found"}
                }
                sys.stdout.write(json.dumps(resp) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    main()
