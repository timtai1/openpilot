# Openpilot / Dragonpilot Drive Viewer (Local Web UI)

A lightweight, modern web-based drive player and telemetry explorer for openpilot and dragonpilot routes.

## Features

- **Dual-Source Support**:
  - **Local Directory**: Browse downloaded driving segments (e.g. `~/Downloads/comma_realdata`).
  - **Remote Comma Device**: Connect over Wi-Fi / SSH by entering the Comma device's IP. Shows connection status and remaining disk space.
- **Multi-Camera Player**:
  - Seamlessly switch between **Road Camera** (`fcamera`), **Wide Camera** (`ecamera`), and **Quick Preview** (`qcamera`).
  - Ultra-fast zero-latency MP4 remuxing with full HTTP 206 range-seeking support.
- **Real-Time Cockpit HUD Overlay**:
  - Digital Speedometer (KM/H) & Cruise Target Speed.
  - Dynamically rotating Steering Wheel matching real vehicle steering angles.
  - G-force / Acceleration bar (m/s²).
  - Radar Lead Car Distance & relative velocity badge with safety alert colors.
  - Gas & Brake pedal visual indicators.
- **Synchronized Telemetry Timeline**:
  - Fast Cap'n Proto / Zstandard log extraction (`qlog.zst` / `rlog.zst`).
  - Interactive multi-metric canvas chart: click anywhere on the chart to jump video playback!
  - Data Selector chips: toggle Speed, Steering Angle, Acceleration, Brake, and Lead Distance.
- **GPS Map Tracking**:
  - Synchronized Leaflet / OpenStreetMap tracking showing vehicle trajectory and realtime position marker.
- **Auto Next Segment**: Continuous playback across multi-segment long drives.

## Getting Started

Run with `uv` (zero manual dependencies installation needed):

```bash
uv run --no-project --with pycapnp --with zstandard python3 tools/web_viewer/server.py
```

Or with Python directly if dependencies are installed:

```bash
python3 tools/web_viewer/server.py
```

Then open your browser at:
[http://localhost:8082](http://localhost:8082)
