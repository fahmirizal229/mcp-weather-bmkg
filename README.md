<div align="center">

# 🌦️ MCP BMKG Weather & Earthquake Radar

<p align="center">
  <strong>Model Context Protocol (FastMCP) server for Indonesian Meteorology, Climatology, and Geophysical Agency (BMKG) Open Data APIs.</strong>
</p>

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastMCP](https://img.shields.io/badge/FastMCP-2.0-blue?style=flat-square)](https://github.com/jlowin/fastmcp)
[![BMKG](https://img.shields.io/badge/BMKG-Open_Data-emerald?style=flat-square)](https://data.bmkg.go.id/)
[![License](https://img.shields.io/badge/License-MIT-emerald?style=flat-square)](LICENSE)

</div>

---

## ✨ Features

- **🌤️ Hyper-Local Weather Forecasts**: Multi-day weather forecasts, temperature, humidity, wind direction, and weather condition codes for major Indonesian cities.
- **🚨 Real-Time Earthquake Radar**: Live earthquake monitoring (Magnitude >= 5.0 and felt earthquakes across Indonesia) with Shakemap URLs and epicenter coordinates.
- **🍃 Air Quality Index (AQI)**: PM2.5 monitoring and health advisory levels.
- **🔌 Universal MCP Compatibility**: Works seamlessly with **Hermes Agent**, **Antigravity CLI**, **Claude Desktop**, and **Cursor IDE**.

---

## 🛠️ Installation & Setup

```bash
# Clone repository
git clone https://github.com/fahmirizal229/mcp-weather-bmkg.git
cd mcp-weather-bmkg

# Run standalone MCP Server
python3 weather_server.py
```

### Claude Desktop / MCP Configuration:
```json
{
  "mcpServers": {
    "weather-bmkg": {
      "command": "python3",
      "args": ["/path/to/mcp-weather-bmkg/weather_server.py"]
    }
  }
}
```
