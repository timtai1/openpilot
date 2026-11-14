# 🐲 dragonpilot (Custom Fork)

> 🤖 All custom features and architectural enhancements in this fork were co-developed with **Gemini 3.8 Flash**.

This repository is a customized fork based on openpilot / dragonpilot (`v0.11.1`), tailored for Comma 3 / 3X devices. It focuses on offline GPS country-based steering wheel initialization with permanent manual locking, full Traditional Chinese localization, CJK bitmap font atlas regeneration, and UI stability improvements.

---

## 📦 Installation Guide

Designed for **Comma 3** and **Comma 3X** devices.

---

### Method 1: On-Device Touchscreen Installation (Recommended & Simplest)

If your device is freshly restored (AGNOS Setup Wizard) or after choosing "Uninstall Software":

1. On the setup screen, tap **"Custom Software"**.
2. Enter either of the following in the URL field:
   * **Short Format (Recommended)**:
     ```text
     timtai1/0.11.1
     ```
   * **Full URL Format**:
     ```text
     https://installer.comma.ai/timtai1/0.11.1
     ```
3. Tap Enter/Continue. The device will automatically download the `0.11.1` branch from `github.com/timtai1/openpilot`, compile, and launch!

---

### Method 2: Installation via SSH (Advanced / Debugging)

#### 1. Fresh Install via SSH
To wipe existing software and install this fork cleanly:
```bash
# 1. SSH into the Comma device
ssh comma@<DEVICE_IP>

# 2. Remove existing openpilot and clone this repository
cd /data
rm -rf openpilot
git clone -b 0.11.1 --depth 1 https://github.com/timtai1/openpilot.git openpilot

# 3. Reboot device to compile and launch
reboot
```

#### 2. In-Place Branch Switch
If your device already has a working openpilot/dragonpilot directory and you wish to switch:
```bash
cd /data/openpilot
git remote set-url origin https://github.com/timtai1/openpilot.git
git fetch origin 0.11.1
git checkout -B 0.11.1 origin/0.11.1
reboot
```

---

## 🚀 Key Custom Features & Updates

### 1. 🛰️ Steering Wheel Position: Offline GPS Country Auto-Initialization + Permanent Manual Lock (Featured)
* **First-Time GPS Country Auto-Detection**:
  * When freshly installed and **not yet manually modified** by the user, once the Comma device acquires its initial GPS fix (`hasFix`), it instantly compares coordinates against an ultra-lightweight offline geographic boundary map.
  * In **Right-Hand Drive (RHD) countries/territories** (Japan, Hong Kong, Macau, UK, Ireland, Australia, New Zealand, Singapore, Thailand, Malaysia, Indonesia, South Africa, etc.), the system **automatically presets the wheel to Right (`Right`)**.
  * In **Left-Hand Drive (LHD) countries** (Taiwan, USA, Canada, Continental Europe, Mainland China, etc.), the system **automatically presets the wheel to Left (`Left`)**.
  * 100% offline calculation with zero network dependencies or privacy risks; works with no SIM card required.
* **Permanent Manual Override Lock**:
  * As soon as the user touches and selects `Left` or `Right` in the dp settings menu, the manual flag is permanently saved (`dp_dev_wheel_position_manually_set = True`).
  * **From that point on, GPS will NEVER override the setting again**, regardless of international travel, tunnels, or GPS signal jitter.
* **Eliminated Dynamic Sensor Misdetection**:
  * The original `policy.py` algorithm that constantly guessed wheel position using the driver camera was completely stripped out, preventing driver monitoring instability caused by backlight, night driving, or body posture.

### 2. 🎡 Manual Wheel Position Toggle ("Wheel on Left or Right?")
* **Custom Settings Toggle**:
  * Added "Wheel on Left or Right?" toggle at the end of the dp settings menu.
  * Options: `Left` (default) and `Right`.
  * Description: *Wheel on left, such as US, TW. Wheel on right like HK, JP.*
  * Settings are persistently stored (`PERSISTENT`) across reboots.

### 3. 🍃 Gentle Acceleration & Gentle Braking
* **Gentle Acceleration Setting**:
  * Added "Gentle Acceleration" setting under dp Longitudinal menu.
  * Six configurable acceleration multipliers: `0.5x`, `0.6x`, `0.7x`, `0.8x`, `0.9x`, `1.0x` (Default is **`0.5x`**).
  * **Applies to Both Takeoff and Mid-Drive Acceleration**: Eliminates aggressive full-throttle surges not just from standstill, but crucially when a lead car changes lanes or speeds away during cruising.
  * **Proportional Multiplier for All Vehicle Types**: Scales both the entire velocity-dependent acceleration limit curve and the MPC virtual cruise target by the multiplier (e.g. at 0.5x, limits are $0.80\text{ m/s}^2$ at 0 km/h, $0.60\text{ m/s}^2$ at 36 km/h, $0.40\text{ m/s}^2$ at 90 km/h), providing silky smooth throttle for EVs, hybrids, and gas cars alike.
  * Resolved '?' character rendering issue by using standard `m/s^2` unit notation.
* **Gentle Braking Setting**:
  * Positioned right below "Gentle Acceleration" in the Longitudinal menu.
  * Three distance multipliers: `1.5x`, `2.0x`, `2.5x` (Default is **`2.0x`**).
  * Smoothly initiates deceleration when approaching stopped or slowing lead vehicles at 1.5x, 2.0x, or 2.5x the normal distance, reducing deceleration proportionally (~`1.0` to `1.67` m/s^2 vs stock aggressive `2.5` m/s^2).
  * **Zero Safety Compromises**: Does not compromise AEB, forward collision warnings (FCW), or emergency evasive braking; if a lead car brakes hard or cuts in closely, bottom-level MPC constraints maintain full maximum braking deceleration (up to `-3.5 ~ -4.0 m/s^2`).

### 4. 🎯 Toyota CC Curve Tuning (Toyota CC 進彎調教)
* **Tailored for High Center of Gravity and Soft Suspension SUVs**:
  * Added "Toyota CC Curve Tuning" switch in dp settings under Lateral controls (`### 橫向控制 ###`), enabled by default (`ON`).
* **Eliminates Curve Entry Overshoot and Abrupt Wobble**:
  * Stock openpilot configures `TOYOTA_COROLLA_TSS2` with a sedan steering ratio of `13.9` (actual Corolla Cross measured ratio is `14.95`), and applies an aggressive lateral jerk feedforward gain of `0.30`. On sharp turns, this kicks excessive steering torque before chassis roll settles, followed by an aggressive PID snap-back ($K_p = 0.80$) that causes passengers to feel uncomfortable steering jerk and wobble.
* **Three-in-One Kinematics and Torque Damping Tuning**:
  * **Corrects Baseline Steering Ratio**: Automatically applies Corolla Cross measured `steerRatio = 14.95`.
  * **Smooths Jerk Feedforward**: Halves curve entry jerk feedforward (`JERK_GAIN = 0.15` vs stock `0.30`) to prevent sudden initial torque overshoot.
  * **Damps High-Speed Proportional Gain**: Softens highway speed ($15 \sim 30\text{ m/s}$ / $54 \sim 108\text{ km/h}$) PID proportional gain from stock `2.0 -> 0.80` to `1.4 -> 0.60`, eliminating overshoot oscillation for smooth, confident curve entry.

### 5. 🇹🇼 Full Traditional Chinese & Multilingual UI Support
* **Localization Engine Refactor**:
  * Rewrote `multilang.py` to directly parse and load `dragonpilot_{lang}.po` files at runtime without requiring precompiled `.mo` binaries.
* **100% Traditional Chinese Translation**:
  * Completed full translation coverage for `dragonpilot_zh-CHT.po`.
  * Resolved the issue where dp settings remained in English even when system language was set to Traditional Chinese.

### 6. 🔤 Bitmap Font Atlas Baking (Resolves '?' Glyph Rendering)
* **Font Processing Tooling**:
  * Updated `selfdrive/assets/fonts/process.py` to automatically harvest all Chinese characters from `.po` files.
* **Regenerated CJK Bitmap Font Atlases**:
  * Re-baked Raylib font atlases (`OpFont-*.fnt` / `OpFont-*.png`) on the Comma device.
  * Completely resolved missing Chinese glyphs rendering as question marks (`?`).

### 7. ⚡ UI Stability Fixes (Crash Prevention)
* **Fixed Menu Crashes**:
  * Resolved `ValueError` caused by string-to-int conversion on boolean parameters (`int("False")`), which previously caused the UI to crash back to the comma boot logo when opening dp settings.

### 8. 🔄 Fast Hot-Reload Deployment Workflow
* **No 10-15 Minute Device Reboot**:
  * Established hot-reload deployment for pure Python, translation, and asset changes.
  * UI restarts and reloads changes via `selfdrive.ui` in ~1 second.

### 9. 🖥️ Local Web Drive & Telemetry Viewer
* **Offline Zero-Latency Video & Telemetry Playback**:
  * Built-in lightweight web server and telemetry dashboard accessible at `http://localhost:8082`.
* **Dual Data Sources & Background Incremental Sync**:
  * 📁 **Local Directory**: Browse downloaded driving segments on your computer (default `~/Downloads/comma_realdata`).
  * 📡 **Remote Comma Device**: Enter the Comma device IP to query and stream `/data/media/0/realdata` directly over local Wi-Fi via SSH.
  * 🔄 **One-Click Background Incremental Sync**: Click "Sync" to download only newly recorded segments from device via `rsync` without interrupting current video playback.
* **Tri-Camera Angle Switching**:
  * `Road` (Standard wide front camera `fcamera.hevc`)
  * `Wide` (Ultra-wide front camera `ecamera.hevc`)
  * `Driver` (Cabin driver monitoring camera `qcamera.ts`)
* **Real-Time Driving Telemetry HUD Overlay**:
  * **Unified Top HUD**: Vehicle speed (km/h), gear indicator (P/R/N/D), Corolla Cross steering wheel rotation icon with exact angle (°).
  * **Pedals & Radar Distance**: Accelerator and brake pedal percentage bars, lead vehicle distance (m).
  * **Autopilot Engagement Indicator**: Luminous green engagement border surrounding the viewport whenever openpilot is actively engaged.
  * **Device Health Monitor**: Real-time display for Comma CPU load, cooling fan RPM, memory (RAM), and SSD storage with instant toggle.
* **Synchronized Interactive Timeline & GPS Trajectory Map**:
  * Interactive chart plotting speed, steering angle, acceleration, pedal inputs, and lead distance with individual metric toggles.
  * Synchronized Leaflet GPS map with real-time vehicle marker movement.
  * Draggable split-pane layout for adjusting video vs. telemetry chart heights with bidirectional responsive resizing.
* **Chronological Sorting**:
  * Sort routes by recording timestamp with one-click `[ ⬇️ Newest First ]` / `[ ⬆️ Oldest First ]` toggle.
* **Quick Start**:
  ```bash
  # Run with uv (auto-installs pycapnp and zstandard without polluting environment):
  uv run --no-project --with pycapnp --with zstandard python3 tools/web_viewer/server.py

  # Or run with standard pip dependencies:
  pip install pycapnp zstandard
  python3 tools/web_viewer/server.py
  ```
  Then open your browser to `http://localhost:8082`.

### 10. 🧹 Offline Loop Recording & Storage Optimization
* **Resolved 95% Disk Full Stall**:
  * Fixed an issue where offline devices (`dp_dev_disable_connect = True`) skipped running `uploader`, leaving orphan `.lock` files that prevented `deleter.py` from purging old segments and caused a 0.1s spin loop consuming ~30% CPU.
  * Added independent lock purging and stale lock clearing so old recordings are cleanly recycled, keeping 20+ GB of free storage.

### 11. 🤖 AI-Assisted Development
* All custom features in this fork—including the offline GPS country bounding algorithms, permanent manual steering position lock, full-speed proportional gentle acceleration scaling, 2x distance early smooth braking kinematics, Toyota Corolla Cross curve entry feedforward and proportional gain damping, runtime Python PO translation parser, Raylib font atlas baking pipeline, local web drive viewer, and on-device hot-reload developer workflows—were developed, debugged, and verified end-to-end with **Gemini 3.8 Flash**.

