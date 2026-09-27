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

### 4. 🇹🇼 Full Traditional Chinese & Multilingual UI Support
* **Localization Engine Refactor**:
  * Rewrote `multilang.py` to directly parse and load `dragonpilot_{lang}.po` files at runtime without requiring precompiled `.mo` binaries.
* **100% Traditional Chinese Translation**:
  * Completed full translation coverage for `dragonpilot_zh-CHT.po`.
  * Resolved the issue where dp settings remained in English even when system language was set to Traditional Chinese.

### 5. 🔤 Bitmap Font Atlas Baking (Resolves '?' Glyph Rendering)
* **Font Processing Tooling**:
  * Updated `selfdrive/assets/fonts/process.py` to automatically harvest all Chinese characters from `.po` files.
* **Regenerated CJK Bitmap Font Atlases**:
  * Re-baked Raylib font atlases (`OpFont-*.fnt` / `OpFont-*.png`) on the Comma device.
  * Completely resolved missing Chinese glyphs rendering as question marks (`?`).

### 6. ⚡ UI Stability Fixes (Crash Prevention)
* **Fixed Menu Crashes**:
  * Resolved `ValueError` caused by string-to-int conversion on boolean parameters (`int("False")`), which previously caused the UI to crash back to the comma boot logo when opening dp settings.

### 7. 🔄 Fast Hot-Reload Deployment Workflow
* **No 10-15 Minute Device Reboot**:
  * Established hot-reload deployment for pure Python, translation, and asset changes.
  * UI restarts and reloads changes via `selfdrive.ui` in ~1 second.

### 8. 🤖 AI-Assisted Development
* All custom features in this fork—including the offline GPS country bounding algorithms, permanent manual steering position lock, full-speed proportional gentle acceleration scaling, 2x distance early smooth braking kinematics, runtime Python PO translation parser, Raylib font atlas baking pipeline, and on-device hot-reload developer workflows—were developed, debugged, and verified end-to-end with **Gemini 3.8 Flash**.

