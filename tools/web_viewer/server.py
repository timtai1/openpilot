#!/usr/bin/env python3
"""
Openpilot / Dragonpilot Local Drive Web Viewer Server
Provides REST APIs for browsing routes, streaming videos, and extracting synchronized telemetry.
"""

import os
import sys
import glob
import json
import time
import shutil
import urllib.parse
import subprocess
import threading
import re
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler

# Auto-detect cereal directory for Cap'n Proto schemas
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
CEREAL_DIR = REPO_ROOT / "cereal"

DEFAULT_LOCAL_PATH = os.path.expanduser("~/Downloads/comma_realdata")
REMOTE_CACHE_DIR = os.path.expanduser("~/.cache/comma_viewer")
PORT = 8082

# Auto-detect SSH keys in ~/.ssh
SSH_KEY = os.environ.get("COMMA_SSH_KEY")
if not SSH_KEY:
    ssh_dir = os.path.expanduser("~/.ssh")
    if os.path.exists(ssh_dir):
        # Look for standard or custom private keys
        candidates = [
            os.path.join(ssh_dir, f) for f in os.listdir(ssh_dir)
            if (f.startswith("id_") or "comma" in f.lower()) and not f.endswith(".pub") and not f.endswith(".known_hosts")
        ]
        if candidates:
            # Prefer id_ed25519 or any specific comma key
            candidates.sort(key=lambda x: ("comma" in x, "ed25519" in x, "rsa" in x), reverse=True)
            SSH_KEY = candidates[0]

def get_ssh_cmd(ip: str, remote_cmd: str):
    cmd = ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=4"]
    if SSH_KEY and os.path.exists(SSH_KEY):
        cmd.extend(["-i", SSH_KEY])
    cmd.extend([f"comma@{ip}", remote_cmd])
    return cmd


class SyncManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.is_running = False
        self.progress_text = "閒置中"
        self.percent = 0
        self.error = None
        self.dest_dir = ""
        self.last_sync_time = None

    def start_sync(self, ip: str, dest_dir: str):
        if not ip:
            return False, "缺少裝置 IP"
        with self.lock:
            if self.is_running:
                return False, "同步已在進行中"
            self.is_running = True
            self.progress_text = "正在準備同步..."
            self.percent = 0
            self.error = None
            self.dest_dir = os.path.expanduser(dest_dir or DEFAULT_LOCAL_PATH)

        thread = threading.Thread(target=self._run_sync, args=(ip, self.dest_dir), daemon=True)
        thread.start()
        return True, "已開始背景同步"

    def _run_sync(self, ip: str, dest: str):
        try:
            os.makedirs(dest, exist_ok=True)
            ssh_opt = "-o StrictHostKeyChecking=no -o ConnectTimeout=5"
            if SSH_KEY and os.path.exists(SSH_KEY):
                ssh_opt = f"-i {SSH_KEY} {ssh_opt}"

            rsync_cmd = [
                "rsync", "-avz", "--partial", "--progress",
                "-e", f"ssh {ssh_opt}",
                f"comma@{ip}:/data/media/0/realdata/",
                f"{dest}/"
            ]

            process = subprocess.Popen(
                rsync_cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1
            )

            for line in process.stdout:
                line = line.strip()
                if not line:
                    continue
                # Parse progress with regex e.g. " 100% 12.34MB/s"
                m_pct = re.search(r"(\d+)%", line)
                if m_pct:
                    try:
                        pct = int(m_pct.group(1))
                        m_spd = re.search(r"(\d+(?:\.\d+)?[kKMGT]?B/s)", line)
                        speed = m_spd.group(1) if m_spd else ""
                        with self.lock:
                            self.percent = pct
                            self.progress_text = f"同步中 {pct}% ({speed})" if speed else f"同步中 {pct}%"
                    except Exception:
                        pass
                else:
                    with self.lock:
                        self.progress_text = f"傳輸中: {line[:35]}"

            process.wait()
            if process.returncode == 0:
                with self.lock:
                    self.is_running = False
                    self.percent = 100
                    self.progress_text = "✅ 同步完成"
                    self.last_sync_time = time.strftime('%H:%M:%S')
            else:
                err = process.stderr.read()
                with self.lock:
                    self.is_running = False
                    self.error = err or "Rsync 結束碼非零"
                    self.progress_text = f"❌ 同步失敗: {self.error[:50]}"
        except Exception as e:
            with self.lock:
                self.is_running = False
                self.error = str(e)
                self.progress_text = f"❌ 異常: {str(e)[:50]}"

    def get_status(self):
        with self.lock:
            return {
                "is_running": self.is_running,
                "progress_text": self.progress_text,
                "percent": self.percent,
                "error": self.error,
                "dest_dir": self.dest_dir,
                "last_sync_time": self.last_sync_time
            }

sync_manager = SyncManager()


def parse_segment_time(seg_name: str, sub_path: str, files: list[str]) -> tuple[float, str, str]:
    """Returns (mtime, time_str, time_short). Prefers timestamp in name, falls back to original files."""
    m = re.search(r"(\d{4}-\d{2}-\d{2})[-_](\d{2})[-:](\d{2})[-:](\d{2})", seg_name)
    if m:
        try:
            dt_str = f"{m.group(1)} {m.group(2)}:{m.group(3)}:{m.group(4)}"
            t_struct = time.strptime(dt_str, "%Y-%m-%d %H:%M:%S")
            mt = time.mktime(t_struct)
            return mt, dt_str, f"{m.group(2)}:{m.group(3)}:{m.group(4)}"
        except Exception:
            pass

    orig_files = [f for f in ["qlog.zst", "rlog.zst", "fcamera.hevc", "ecamera.hevc", "dcamera.hevc", "qcamera.ts"] if f in files]
    if orig_files and os.path.exists(sub_path):
        try:
            mt = min([os.path.getmtime(os.path.join(sub_path, f)) for f in orig_files])
            return mt, time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mt)), time.strftime('%H:%M:%S', time.localtime(mt))
        except Exception:
            pass

    mt = os.path.getmtime(sub_path) if os.path.exists(sub_path) else 0
    t_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mt)) if mt else ""
    t_short = time.strftime('%H:%M:%S', time.localtime(mt)) if mt else ""
    return mt, t_str, t_short


def sanitize_route_segments(segments: list[dict]) -> tuple[float, str]:
    """Repairs pre-GPS cold-boot segment timestamps (e.g. 21:47 RTC) using contiguous 60s offsets from GPS-locked segments."""
    if not segments:
        return 0, ""

    def get_idx(s):
        try:
            return int(s.get("segment_idx", 0))
        except Exception:
            return 0

    segments.sort(key=get_idx)

    # Find the most reliable reference timestamp in this route (latest segments almost always have GPS lock)
    max_mtime = max((s.get("mtime", 0) for s in segments), default=0)
    if max_mtime <= 0:
        return 0, ""

    # Find first segment whose timestamp is valid (within 2 days of route max mtime)
    ref_seg = None
    for s in segments:
        s_mt = s.get("mtime", 0)
        if s_mt > 0 and abs(max_mtime - s_mt) < 86400 * 2:
            ref_seg = s
            break

    if ref_seg:
        ref_idx = get_idx(ref_seg)
        ref_mt = ref_seg["mtime"]
        for s in segments:
            idx = get_idx(s)
            s_mt = s.get("mtime", 0)
            expected_mt = ref_mt + (idx - ref_idx) * 60.0
            # If timestamp is missing or wildly divergent (> 6h off expected contiguous time)
            if s_mt <= 0 or abs(s_mt - expected_mt) > 3600 * 6:
                s["mtime"] = expected_mt
                s["time_str"] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(expected_mt))
                s["time_short"] = time.strftime('%H:%M:%S', time.localtime(expected_mt))

    route_mtime = segments[0]["mtime"]
    date_str = segments[0]["time_str"][:16] if segments[0].get("time_str") else ""
    return route_mtime, date_str

class TelemetryExtractor:
    def __init__(self):
        self._capnp_loaded = False
        self._log_capnp = None

    def _init_capnp(self):
        if self._capnp_loaded:
            return True
        try:
            import capnp
            capnp.remove_import_hook()
            schema_path = os.path.join(CEREAL_DIR, "log.capnp")
            if os.path.exists(schema_path):
                self._log_capnp = capnp.load(schema_path)
                self._capnp_loaded = True
                return True
        except Exception as e:
            print(f"[Extractor] Error loading capnp: {e}")
        return False

    def extract(self, segment_dir: str):
        cache_file = os.path.join(segment_dir, ".telemetry.json")
        if os.path.exists(cache_file):
            try:
                with open(cache_file, "r") as f:
                    cdata = json.load(f)
                    if cdata and cdata.get("points_count", 0) > 0 and cdata.get("duration", 0) < 300:
                        # Ensure engaged and gear keys are in cache points
                        if len(cdata.get("timeline", [])) > 0 and "engaged" in cdata["timeline"][0] and "gear" in cdata["timeline"][0]:
                            return cdata
            except Exception:
                pass

        if not self._init_capnp():
            return None

        # Prefer rlog.zst (full data), fallback to qlog.zst
        log_files = []
        for name in ["rlog.zst", "qlog.zst"]:
            candidate = os.path.join(segment_dir, name)
            if os.path.exists(candidate) and os.path.getsize(candidate) > 100:
                log_files.append(candidate)

        if not log_files:
            return None

        import zstandard as zstd
        import io

        events = []
        for log_file in log_files:
            try:
                with open(log_file, "rb") as f:
                    data = f.read()
                dctx = zstd.ZstdDecompressor()
                decomp = b""
                try:
                    with dctx.stream_reader(io.BytesIO(data)) as reader:
                        decomp = reader.read()
                except Exception:
                    try:
                        decomp = dctx.decompress(data, max_output_size=120 * 1024 * 1024)
                    except Exception:
                        pass

                if not decomp:
                    continue

                # Parse events with truncation tolerance (sudden power off cutoffs)
                parsed_evts = []
                try:
                    for evt in self._log_capnp.Event.read_multiple_bytes(decomp):
                        parsed_evts.append(evt)
                except Exception:
                    # Message ends prematurely at tail - perfectly normal for abrupt shutdown
                    pass

                if any(e.which() == "carState" for e in parsed_evts):
                    events = parsed_evts
                    break
                elif not events:
                    events = parsed_evts
            except Exception as e:
                print(f"[Extractor] Error reading {log_file}: {e}")

        if not events:
            return None

        try:
            # Find first vehicle sensor event to anchor t=0
            first_mono = None
            for evt in events:
                if evt.which() in ("carState", "controlsState", "selfdriveState", "radarState", "cameraOdometry"):
                    first_mono = evt.logMonoTime
                    break
            if first_mono is None:
                first_mono = events[0].logMonoTime

            # Temporary storage with downsampling (~10Hz)
            samples = {}

            for evt in events:
                mono = evt.logMonoTime
                t_rel = (mono - first_mono) / 1e9
                # Discard events with negative relative time or outliers beyond 120s
                if t_rel < -0.5 or t_rel > 120:
                    continue
                t_rel = max(0.0, t_rel)

                bucket = round(t_rel * 10) / 10.0  # 0.1s bucket
                if bucket not in samples:
                    samples[bucket] = {"t": bucket}
                sample = samples[bucket]

                w = evt.which()
                if w == "selfdriveState":
                    sds = evt.selfdriveState
                    sample["engaged"] = bool(sds.enabled)
                    if hasattr(sds, "active"):
                        sample["active"] = bool(sds.active)
                elif w == "controlsState":
                    ctrl = evt.controlsState
                    if hasattr(ctrl, "enabled"):
                        sample["engaged"] = bool(ctrl.enabled)
                elif w == "carState":
                    cs = evt.carState
                    sample["speed"] = round(cs.vEgo * 3.6, 1)
                    sample["steer"] = round(cs.steeringAngleDeg, 1)
                    sample["steer_torque"] = round(cs.steeringTorque, 2)
                    sample["steer_pressed"] = bool(cs.steeringPressed)
                    sample["aEgo"] = round(cs.aEgo, 2)
                    sample["gas_pressed"] = bool(cs.gasPressed)
                    sample["brake_pressed"] = bool(cs.brakePressed)
                    sample["brake"] = round(cs.brake * 100, 1) if hasattr(cs, "brake") else (100.0 if cs.brakePressed else 0.0)
                    if hasattr(cs, "vCruise"):
                        sample["vCruise"] = round(cs.vCruise, 1)
                    if hasattr(cs, "leftBlinker") and hasattr(cs, "rightBlinker"):
                        sample["blinker"] = -1 if cs.leftBlinker else (1 if cs.rightBlinker else 0)
                    if hasattr(cs, "cruiseState") and hasattr(cs.cruiseState, "enabled"):
                        sample["cruise_enabled"] = bool(cs.cruiseState.enabled)
                    if hasattr(cs, "gearShifter"):
                        g_str = str(cs.gearShifter).lower()
                        gear_map = {"park": "P", "reverse": "R", "neutral": "N", "drive": "D", "sport": "S", "low": "L", "brake": "B"}
                        sample["gear"] = gear_map.get(g_str, g_str.upper()[:1] if g_str else "D")
                elif w == "deviceState":
                    ds = evt.deviceState
                    dev = {}
                    if hasattr(ds, "cpuTempC") and len(ds.cpuTempC) > 0:
                        dev["cpu_temp"] = round(float(max(ds.cpuTempC)), 1)
                    if hasattr(ds, "gpuTempC") and len(ds.gpuTempC) > 0:
                        dev["gpu_temp"] = round(float(max(ds.gpuTempC)), 1)
                    if hasattr(ds, "memoryUsagePercent"):
                        dev["mem_pct"] = int(ds.memoryUsagePercent)
                    if hasattr(ds, "freeSpacePercent"):
                        dev["storage_pct"] = round(float(ds.freeSpacePercent), 1)
                    if hasattr(ds, "fanSpeedPercentDesired"):
                        dev["fan_pct"] = int(ds.fanSpeedPercentDesired)
                    sample["device"] = dev
                elif w == "radarState":
                    rs = evt.radarState
                    if rs.leadOne.status:
                        sample["lead_d"] = round(rs.leadOne.dRel, 1)
                        sample["lead_v"] = round(rs.leadOne.vRel * 3.6, 1)
                    else:
                        sample["lead_d"] = None
                        sample["lead_v"] = None
                elif w == "gpsLocation" or w == "gpsLocationExternal":
                    gps = getattr(evt, w)
                    if hasattr(gps, "latitude") and hasattr(gps, "longitude"):
                        if abs(gps.latitude) > 0.001 and abs(gps.longitude) > 0.001:
                            sample["lat"] = round(gps.latitude, 6)
                            sample["lon"] = round(gps.longitude, 6)
                            sample["bearing"] = round(getattr(gps, "bearingDeg", 0), 1)

            # Sort by time and interpolate missing fields
            sorted_times = sorted(samples.keys())
            timeline = []
            last_valid = {
                "speed": 0, "steer": 0, "aEgo": 0, "gas_pressed": False,
                "brake_pressed": False, "brake": 0, "vCruise": 0, "lead_d": None,
                "lead_v": None, "lat": None, "lon": None, "bearing": 0, "blinker": 0,
                "engaged": False, "gear": "D",
                "device": {"cpu_temp": None, "gpu_temp": None, "mem_pct": None, "storage_pct": None, "fan_pct": None}
            }

            for t in sorted_times:
                s = samples[t]
                pt = {"t": t}
                for k in ["speed", "steer", "aEgo", "gas_pressed", "brake_pressed", "brake", "vCruise", "lead_d", "lead_v", "blinker", "engaged", "gear", "device"]:
                    if k in s:
                        if k == "device" and isinstance(s[k], dict):
                            last_valid["device"].update(s[k])
                        else:
                            last_valid[k] = s[k]
                    elif k == "engaged" and ("cruise_enabled" in s):
                        last_valid[k] = s["cruise_enabled"]
                    if k == "device":
                        pt[k] = dict(last_valid[k])
                    else:
                        pt[k] = last_valid[k]

                if "lat" in s:
                    pt["lat"] = s["lat"]
                    pt["lon"] = s["lon"]
                    pt["bearing"] = s.get("bearing", 0)
                    last_valid["lat"] = s["lat"]
                    last_valid["lon"] = s["lon"]
                    last_valid["bearing"] = pt["bearing"]
                elif last_valid["lat"] is not None:
                    pt["lat"] = last_valid["lat"]
                    pt["lon"] = last_valid["lon"]
                    pt["bearing"] = last_valid["bearing"]

                timeline.append(pt)

            result = {
                "segment": os.path.basename(segment_dir),
                "duration": round(sorted_times[-1], 1) if sorted_times else 0,
                "points_count": len(timeline),
                "timeline": timeline
            }

            # Save cache
            try:
                with open(cache_file, "w") as f:
                    json.dump(result, f)
            except Exception:
                pass

            return result
        except Exception as e:
            print(f"[Extractor] Error processing {segment_dir}: {e}")
            return None

            return result
        except Exception as e:
            print(f"[Extractor] Error processing {log_file}: {e}")
            return None


extractor = TelemetryExtractor()


def ensure_mp4(segment_dir: str, cam: str) -> str:
    """Ensure an MP4 file exists for the camera; remuxes from .hevc or .ts if needed."""
    mp4_path = os.path.join(segment_dir, f"{cam}.mp4")
    if os.path.exists(mp4_path) and os.path.getsize(mp4_path) > 1000:
        return mp4_path

    src_file = None
    if cam in ["fcamera", "ecamera", "dcamera"]:
        candidate = os.path.join(segment_dir, f"{cam}.hevc")
        if os.path.exists(candidate):
            src_file = candidate
    elif cam == "qcamera":
        candidate = os.path.join(segment_dir, "qcamera.ts")
        if os.path.exists(candidate):
            src_file = candidate

    if not src_file:
        return ""

    ffmpeg = shutil.which("ffmpeg") or "/opt/homebrew/bin/ffmpeg"
    if not os.path.exists(ffmpeg):
        return src_file  # Fallback to source

    try:
        # Fast remux without re-encoding
        cmd = [ffmpeg, "-y", "-i", src_file, "-c", "copy", mp4_path]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
        if os.path.exists(mp4_path):
            return mp4_path
    except Exception as e:
        print(f"[FFmpeg] Remux failed for {src_file}: {e}")

    return src_file


class ViewerHandler(BaseHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Range")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()

    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        qs = urllib.parse.parse_qs(parsed.query)

        if path == "/" or path == "/index.html":
            self.serve_static("web/index.html", "text/html")
        elif path.startswith("/static/"):
            rel_file = path[8:]
            self.serve_static(os.path.join("web", rel_file))
        elif path == "/api/sources":
            self.handle_api_sources()
        elif path == "/api/device/test":
            self.handle_api_device_test(qs)
        elif path == "/api/routes":
            self.handle_api_routes(qs)
        elif path == "/api/telemetry":
            self.handle_api_telemetry(qs)
        elif path == "/api/video":
            self.handle_api_video(qs)
        elif path == "/api/sync/status":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(sync_manager.get_status()).encode("utf-8"))
        elif path == "/api/sync/start":
            ip = qs.get("ip", [""])[0].strip()
            dest = qs.get("dest", [DEFAULT_LOCAL_PATH])[0].strip()
            success, msg = sync_manager.start_sync(ip, dest)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "message": msg, "status": sync_manager.get_status()}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def do_POST(self):
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        if path == "/api/sync/start":
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length).decode("utf-8") if content_length > 0 else ""
            data = {}
            if body:
                try:
                    data = json.loads(body)
                except Exception:
                    pass
            qs = urllib.parse.parse_qs(parsed.query)
            ip = data.get("ip") or qs.get("ip", [""])[0].strip()
            dest = data.get("dest") or qs.get("dest", [DEFAULT_LOCAL_PATH])[0].strip()
            success, msg = sync_manager.start_sync(ip, dest)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"success": success, "message": msg, "status": sync_manager.get_status()}).encode("utf-8"))
        else:
            self.send_error(404, "Not Found")

    def serve_static(self, rel_path: str, content_type=None):
        base_dir = Path(__file__).resolve().parent
        full_path = base_dir / rel_path
        if not full_path.exists():
            self.send_error(404, "File not found")
            return

        if not content_type:
            if rel_path.endswith(".html"): content_type = "text/html"
            elif rel_path.endswith(".js"): content_type = "application/javascript"
            elif rel_path.endswith(".css"): content_type = "text/css"
            elif rel_path.endswith(".json"): content_type = "application/json"
            else: content_type = "application/octet-stream"

        with open(full_path, "rb") as f:
            data = f.read()
        self.send_response(200)
        self.send_header("Content-Type", f"{content_type}; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def handle_api_sources(self):
        sources = [
            {"name": "Local Downloaded (`~/Downloads/comma_realdata`)", "type": "local", "path": DEFAULT_LOCAL_PATH, "exists": os.path.exists(DEFAULT_LOCAL_PATH)},
            {"name": "Comma Device (Remote over Wi-Fi/SSH)", "type": "remote"}
        ]
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"sources": sources}).encode("utf-8"))

    def handle_api_device_test(self, qs):
        ip = qs.get("ip", [""])[0].strip()
        if not ip:
            self.send_response(400)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"connected": False, "error": "Missing IP parameter"}).encode("utf-8"))
            return
        cmd = get_ssh_cmd(ip, "df -h /data | tail -n 1")
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if res.returncode == 0:
                parts = res.stdout.strip().split()
                storage = f"Total: {parts[1]}, Used: {parts[2]} ({parts[4]}), Free: {parts[3]}" if len(parts) >= 5 else res.stdout.strip()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"connected": True, "ip": ip, "storage": storage}).encode("utf-8"))
                return
            else:
                err = res.stderr.strip() or "Connection failed"
        except Exception as e:
            err = str(e)

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"connected": False, "ip": ip, "error": err}).encode("utf-8"))

    def handle_api_routes(self, qs):
        source = qs.get("source", ["local"])[0]
        ip = qs.get("ip", [""])[0].strip()

        if source == "remote":
            if not ip:
                self.send_response(400)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"routes": [], "error": "Missing IP parameter"}).encode("utf-8"))
                return
            # Query routes directly on remote device via SSH
            remote_script = (
                "python3 -c \""
                "import os, json; root = '/data/media/0/realdata'; "
                "print(json.dumps([{'name': d, 'files': os.listdir(os.path.join(root, d)), 'mtime': min([os.path.getmtime(os.path.join(root, d, f)) for f in ['qlog.zst', 'rlog.zst', 'fcamera.hevc', 'ecamera.hevc', 'dcamera.hevc', 'qcamera.ts'] if os.path.exists(os.path.join(root, d, f))] or [os.path.getmtime(os.path.join(root, d))])} for d in sorted(os.listdir(root)) if os.path.isdir(os.path.join(root, d))] if os.path.exists(root) else []))\""
            )
            cmd = get_ssh_cmd(ip, remote_script)
            try:
                res = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
                if res.returncode != 0:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(json.dumps({"routes": [], "error": f"Failed to connect to {ip}: {res.stderr.strip()}"}).encode("utf-8"))
                    return
                remote_subdirs = json.loads(res.stdout)
            except Exception as e:
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps({"routes": [], "error": f"Remote query failed: {str(e)}"}).encode("utf-8"))
                return

            routes_map = {}
            for item in remote_subdirs:
                d = item["name"]
                files = item["files"]
                parts = d.split("--")
                route_id = f"{parts[0]}--{parts[1]}" if len(parts) >= 3 else d
                seg_idx = parts[2] if len(parts) >= 3 else "0"

                mt, time_str, time_short = parse_segment_time(d, "", files)
                if not mt:
                    mt = item.get("mtime", 0)
                    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(mt)) if mt else ""
                    time_short = time.strftime('%H:%M:%S', time.localtime(mt)) if mt else ""

                seg_info = {
                    "name": d,
                    "segment_idx": seg_idx,
                    "has_fcamera": any(f.startswith("fcamera") for f in files),
                    "has_ecamera": any(f.startswith("ecamera") for f in files),
                    "has_dcamera": any(f.startswith("dcamera") for f in files),
                    "has_qcamera": any(f.startswith("qcamera") for f in files),
                    "has_log": any(f.endswith(".zst") for f in files),
                    "is_remote": True,
                    "mtime": mt,
                    "time_str": time_str,
                    "time_short": time_short
                }
                if route_id not in routes_map:
                    routes_map[route_id] = {
                        "route_id": route_id,
                        "segments": [],
                        "mtime": seg_info["mtime"],
                        "date_str": seg_info["time_str"][:16] if seg_info["time_str"] else route_id
                    }
                routes_map[route_id]["segments"].append(seg_info)
                if seg_info["mtime"] > routes_map[route_id]["mtime"]:
                    routes_map[route_id]["mtime"] = seg_info["mtime"]
                    routes_map[route_id]["date_str"] = seg_info["time_str"][:16]

            routes_list = list(routes_map.values())
            for r in routes_list:
                r["mtime"], r["date_str"] = sanitize_route_segments(r["segments"])
            routes_list.sort(key=lambda r: r["mtime"], reverse=True)
            for r in routes_list:
                r["segments"].sort(key=lambda s: int(s["segment_idx"]) if s["segment_idx"].isdigit() else s["segment_idx"])

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"base_path": f"comma@{ip}:/data/media/0/realdata", "is_remote": True, "routes": routes_list}).encode("utf-8"))
            return

        # Local routes
        dir_path = qs.get("path", [DEFAULT_LOCAL_PATH])[0]
        dir_path = os.path.expanduser(dir_path)

        if not os.path.exists(dir_path):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"routes": [], "error": "Directory does not exist"}).encode("utf-8"))
            return

        subdirs = sorted([d for d in os.listdir(dir_path) if os.path.isdir(os.path.join(dir_path, d))])
        routes_map = {}

        for d in subdirs:
            full_sub = os.path.join(dir_path, d)
            files = os.listdir(full_sub)

            parts = d.split("--")
            route_id = f"{parts[0]}--{parts[1]}" if len(parts) >= 3 else d
            seg_idx = parts[2] if len(parts) >= 3 else "0"

            mt, time_str, time_short = parse_segment_time(d, full_sub, files)

            seg_info = {
                "name": d,
                "segment_idx": seg_idx,
                "has_fcamera": "fcamera.hevc" in files or "fcamera.mp4" in files,
                "has_ecamera": "ecamera.hevc" in files or "ecamera.mp4" in files,
                "has_dcamera": "dcamera.hevc" in files or "dcamera.mp4" in files,
                "has_qcamera": "qcamera.ts" in files or "qcamera.mp4" in files,
                "has_log": "qlog.zst" in files or "rlog.zst" in files,
                "cached_telemetry": ".telemetry.json" in files,
                "is_remote": False,
                "mtime": mt,
                "time_str": time_str,
                "time_short": time_short
            }

            if route_id not in routes_map:
                routes_map[route_id] = {
                    "route_id": route_id,
                    "segments": [],
                    "mtime": seg_info["mtime"],
                    "date_str": seg_info["time_str"][:16] if seg_info["time_str"] else route_id
                }
            routes_map[route_id]["segments"].append(seg_info)
            if seg_info["mtime"] > routes_map[route_id]["mtime"]:
                routes_map[route_id]["mtime"] = seg_info["mtime"]
                routes_map[route_id]["date_str"] = seg_info["time_str"][:16]

        routes_list = list(routes_map.values())
        for r in routes_list:
            r["mtime"], r["date_str"] = sanitize_route_segments(r["segments"])
        routes_list.sort(key=lambda r: r["mtime"], reverse=True)
        for r in routes_list:
            r["segments"].sort(key=lambda s: int(s["segment_idx"]) if s["segment_idx"].isdigit() else s["segment_idx"])

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"base_path": dir_path, "is_remote": False, "routes": routes_list}).encode("utf-8"))

    def handle_api_telemetry(self, qs):
        source = qs.get("source", ["local"])[0]
        ip = qs.get("ip", [""])[0].strip()
        seg_name = qs.get("segment", [""])[0]

        if not seg_name:
            self.send_error(400, "Missing segment parameter")
            return

        if source == "remote":
            if not ip:
                self.send_error(400, "Missing IP parameter")
                return
            cache_dir = os.path.join(REMOTE_CACHE_DIR, ip, seg_name)
            os.makedirs(cache_dir, exist_ok=True)
            cached_json = os.path.join(cache_dir, ".telemetry.json")
            if not os.path.exists(cached_json):
                # Fetch remote qlog.zst via scp
                remote_file = f"comma@{ip}:/data/media/0/realdata/{seg_name}/qlog.zst"
                dest_file = os.path.join(cache_dir, "qlog.zst")
                scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=4"]
                if SSH_KEY: scp_cmd.extend(["-i", SSH_KEY])
                scp_cmd.extend([remote_file, dest_file])
                subprocess.run(scp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
            data = extractor.extract(cache_dir)
        else:
            base_dir = os.path.expanduser(qs.get("path", [DEFAULT_LOCAL_PATH])[0])
            seg_dir = os.path.join(base_dir, seg_name)
            if not os.path.exists(seg_dir):
                self.send_error(404, "Segment not found")
                return
            data = extractor.extract(seg_dir)

        if not data:
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps({"error": "No telemetry found or parsing failed"}).encode("utf-8"))
            return

        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def handle_api_video(self, qs):
        source = qs.get("source", ["local"])[0]
        ip = qs.get("ip", [""])[0].strip()
        seg_name = qs.get("segment", [""])[0]
        cam = qs.get("cam", ["fcamera"])[0]

        if not seg_name:
            self.send_error(400, "Missing segment parameter")
            return

        if source == "remote":
            if not ip:
                self.send_error(400, "Missing IP parameter")
                return
            cache_dir = os.path.join(REMOTE_CACHE_DIR, ip, seg_name)
            os.makedirs(cache_dir, exist_ok=True)
            mp4_file = os.path.join(cache_dir, f"{cam}.mp4")
            if not os.path.exists(mp4_file):
                # Download remote file
                ext = "ts" if cam == "qcamera" else "hevc"
                src_filename = f"{cam}.{ext}"
                remote_file = f"comma@{ip}:/data/media/0/realdata/{seg_name}/{src_filename}"
                dest_file = os.path.join(cache_dir, src_filename)
                if not os.path.exists(dest_file):
                    scp_cmd = ["scp", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=6"]
                    if SSH_KEY: scp_cmd.extend(["-i", SSH_KEY])
                    scp_cmd.extend([remote_file, dest_file])
                    subprocess.run(scp_cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
                ensure_mp4(cache_dir, cam)
            target_file = mp4_file if os.path.exists(mp4_file) else os.path.join(cache_dir, f"{cam}.{ext}")
        else:
            base_dir = os.path.expanduser(qs.get("path", [DEFAULT_LOCAL_PATH])[0])
            seg_dir = os.path.join(base_dir, seg_name)
            target_file = ensure_mp4(seg_dir, cam)

        if not target_file or not os.path.exists(target_file):
            self.send_error(404, f"Video {cam} not found")
            return

        self.serve_file_with_range(target_file)

    def serve_file_with_range(self, filepath: str):
        file_size = os.path.getsize(filepath)
        range_header = self.headers.get("Range")

        mime = "video/mp4"
        if filepath.endswith(".ts"): mime = "video/mp2t"
        elif filepath.endswith(".hevc"): mime = "video/hevc"

        try:
            if range_header:
                range_match = range_header.strip().replace("bytes=", "").split("-")
                start = int(range_match[0]) if range_match[0] else 0
                end = int(range_match[1]) if len(range_match) > 1 and range_match[1] else file_size - 1
                length = end - start + 1

                self.send_response(206)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Range", f"bytes {start}-{end}/{file_size}")
                self.send_header("Content-Length", str(length))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(filepath, "rb") as f:
                    f.seek(start)
                    sent = 0
                    while sent < length:
                        chunk = f.read(min(64 * 1024, length - sent))
                        if not chunk: break
                        self.wfile.write(chunk)
                        sent += len(chunk)
            else:
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(file_size))
                self.send_header("Accept-Ranges", "bytes")
                self.end_headers()

                with open(filepath, "rb") as f:
                    shutil.copyfileobj(f, self.wfile)
        except (BrokenPipeError, ConnectionResetError):
            pass


def run_server():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), ViewerHandler)
    print(f"\n=======================================================")
    print(f"🚀 Openpilot Drive Viewer Running at: http://localhost:{PORT}")
    print(f"📂 Default Data Path: {DEFAULT_LOCAL_PATH}")
    print(f"=======================================================\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping viewer server...")
        server.server_close()


if __name__ == "__main__":
    run_server()
