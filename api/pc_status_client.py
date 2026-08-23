import json
import math
import os
import random
import sys
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
import requests
from PyQt5.QtCore import QObject, QThread, QTimer, pyqtSignal
from config import config

try:
    import psutil
except ImportError:
    psutil = None

if sys.platform == "win32":
    import ctypes

    def scan_host_system_disks() -> list[dict]:
        disks = []
        try:
            buf = ctypes.create_unicode_buffer(2048)
            n = ctypes.windll.kernel32.GetLogicalDriveStringsW(ctypes.sizeof(buf), buf)
            drives = [d for d in buf[:n].split("\x00") if d]
            for d in drives:
                dtype = ctypes.windll.kernel32.GetDriveTypeW(d)
                if dtype == 3:
                    vol_buf = ctypes.create_unicode_buffer(1024)
                    ctypes.windll.kernel32.GetVolumeInformationW(
                        d, vol_buf, ctypes.sizeof(vol_buf), None, None, None, None, 0
                    )
                    free_caller = ctypes.c_ulonglong(0)
                    total_bytes = ctypes.c_ulonglong(0)
                    total_free = ctypes.c_ulonglong(0)
                    ret = ctypes.windll.kernel32.GetDiskFreeSpaceExW(
                        d,
                        ctypes.byref(free_caller),
                        ctypes.byref(total_bytes),
                        ctypes.byref(total_free),
                    )
                    if ret and total_bytes.value > 0:
                        drive_letter = d.rstrip("\\/").strip()
                        name = vol_buf.value.strip() if vol_buf.value else ""
                        disks.append({
                            "label": drive_letter,
                            "name": name,
                            "totalBytes": total_bytes.value,
                            "freeBytes": total_free.value,
                        })
        except Exception:
            pass

        if not disks:
            disks = [
                {"label": "C:", "name": "", "totalBytes": 1024 * (1024**3), "freeBytes": 450 * (1024**3)},
                {"label": "D:", "name": "", "totalBytes": 2048 * (1024**3), "freeBytes": 980 * (1024**3)},
            ]
        return disks
else:
    def scan_host_system_disks() -> list[dict]:
        disks = []
        if psutil is not None:
            try:
                network_fs = {"nfs", "cifs", "smbfs", "nfs4", "fuse.sshfs", "afp"}
                for p in psutil.disk_partitions(all=False):
                    if "cdrom" in p.opts or (hasattr(p, "fstype") and p.fstype in network_fs) or p.fstype == "":
                        continue
                    try:
                        usage = psutil.disk_usage(p.mountpoint)
                        if usage.total > 0:
                            drive_letter = p.mountpoint.rstrip("\\/").strip()
                            disks.append({
                                "label": drive_letter,
                                "name": "",
                                "totalBytes": usage.total,
                                "freeBytes": usage.free,
                            })
                    except Exception:
                        continue
            except Exception:
                pass
        if not disks:
            disks = [{"label": "/", "name": "Root", "totalBytes": 1024 * (1024**3), "freeBytes": 450 * (1024**3)}]
        return disks


class PcStatusWorker(QThread):
    finished = pyqtSignal(dict)
    failed = pyqtSignal(str)

    def __init__(self, endpoint: str, token: str, parent=None):
        super().__init__(parent)
        self.endpoint = endpoint
        self.token = token

    def run(self):
        try:
            headers = {}
            if self.token:
                headers["Authorization"] = f"Bearer {self.token}"
            resp = requests.get(self.endpoint, headers=headers, timeout=2)
            if resp.status_code == 200:
                self.finished.emit(resp.json())
            else:
                self.failed.emit(f"HTTP {resp.status_code}")
        except Exception as e:
            self.failed.emit(str(e))


class PcStatusServerThread(QThread):
    status_received = pyqtSignal(dict)

    def __init__(self, port: int = 3000, token: str = "", stale_after_ms: int = 30000, parent=None):
        super().__init__(parent)
        self.port = port
        self.token = token
        self.stale_after_ms = stale_after_ms
        self.httpd = None
        self.last_payload = None
        self.updated_at = None
        self.last_received_ts = 0.0

    def run(self):
        worker = self

        class StatusHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass

            def do_GET(self):
                if self.path.rstrip("/") != "/api/pc-status":
                    self.send_response(404)
                    self.end_headers()
                    return

                now = time.time()
                is_stale = (
                    worker.last_payload is None
                    or (now - worker.last_received_ts) > (worker.stale_after_ms / 1000.0)
                )

                response_data = {
                    "data": None if is_stale else worker.last_payload,
                    "online": not is_stale,
                    "stale": is_stale,
                    "updatedAt": worker.updated_at,
                }
                body = json.dumps(response_data).encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "application/json; charset=utf-8")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def do_POST(self):
                if self.path.rstrip("/") != "/api/pc-status":
                    self.send_response(404)
                    self.end_headers()
                    return

                if worker.token:
                    auth = self.headers.get("Authorization", "")
                    if auth != f"Bearer {worker.token}":
                        self.send_response(401)
                        self.end_headers()
                        return

                length = int(self.headers.get("Content-Length", 0))
                body = self.rfile.read(length)
                try:
                    payload = json.loads(body.decode("utf-8"))
                    worker.updated_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
                    worker.last_received_ts = time.time()
                    if isinstance(payload, dict):
                        if "data" in payload or "Data" in payload:
                            worker.last_payload = payload.get("data") or payload.get("Data")
                        else:
                            worker.last_payload = payload
                    worker.status_received.emit(payload)
                    self.send_response(202)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"ok":true}')
                except Exception:
                    self.send_response(400)
                    self.end_headers()

        try:
            self.httpd = HTTPServer(("0.0.0.0", self.port), StatusHandler)
            self.httpd.serve_forever()
        except Exception:
            pass

    def stop(self):
        if self.httpd:
            try:
                self.httpd.shutdown()
                self.httpd.server_close()
            except Exception:
                pass


class MockPcMetricsGenerator:
    def __init__(self):
        self.uptime = 18450
        self.cur_cpu = 18.0
        self.cur_gpu = 32.0
        self.cur_ram = 46.0
        self.cur_vram = 5.4 * (1024**3)
        self.cur_gpu_temp = 48.5
        self.cur_tx = 450000
        self.cur_rx = 1850000

        self.discovered_disks = scan_host_system_disks()
        self.disk_loads = {d["label"]: 0.0 for d in self.discovered_disks}

    def get_payload(self) -> dict:
        self.uptime += 1
        
        cpu_target = max(5.0, min(95.0, self.cur_cpu + random.uniform(-12.0, 14.0)))
        self.cur_cpu = round(0.7 * self.cur_cpu + 0.3 * cpu_target, 1)

        gpu_target = max(10.0, min(98.0, self.cur_gpu + random.uniform(-15.0, 18.0)))
        self.cur_gpu = round(0.75 * self.cur_gpu + 0.25 * gpu_target, 1)
        
        ram_target = max(40.0, min(65.0, self.cur_ram + random.uniform(-2.0, 2.5)))
        self.cur_ram = round(0.9 * self.cur_ram + 0.1 * ram_target, 1)

        vram_target = (self.cur_gpu / 100.0 * 6.0 + 3.2) * (1024**3)
        self.cur_vram = 0.85 * self.cur_vram + 0.15 * vram_target

        self.cur_gpu_temp = round(42.0 + (self.cur_gpu / 100.0) * 26.0 + random.uniform(-1.0, 1.0), 1)

        tx_target = max(15000, random.uniform(50000, 2500000))
        rx_target = max(80000, random.uniform(200000, 12500000))
        self.cur_tx = int(0.7 * self.cur_tx + 0.3 * tx_target)
        self.cur_rx = int(0.7 * self.cur_rx + 0.3 * rx_target)

        total_ram = 32 * (1024**3)
        used_ram = int((self.cur_ram / 100.0) * total_ram)
        swap_used = int(2.4 * (1024**3) + random.uniform(-0.1, 0.1) * (1024**3))

        for drive in self.disk_loads:
            if random.random() < 0.35:
                target = random.uniform(10.0, 85.0)
            else:
                target = random.uniform(0.0, 3.0)
            self.disk_loads[drive] = round(0.6 * self.disk_loads[drive] + 0.4 * target, 1)

        disks_payload = []
        for disk_info in self.discovered_disks:
            label = disk_info["label"]
            disks_payload.append({
                "label": label,
                "name": disk_info["name"],
                "totalBytes": disk_info["totalBytes"],
                "freeBytes": disk_info["freeBytes"],
                "usagePercent": self.disk_loads.get(label, 0.0),
            })

        return {
            "online": True,
            "stale": False,
            "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "data": {
                "host": "DESKTOP-MAIN",
                "uptimeSeconds": self.uptime,
                "cpu": {
                    "usagePercent": self.cur_cpu,
                },
                "memory": {
                    "totalBytes": total_ram,
                    "usedBytes": used_ram,
                    "freeBytes": total_ram - used_ram,
                    "commitUsedBytes": used_ram + swap_used,
                },
                "swap": {
                    "totalBytes": 16 * (1024**3),
                    "usedBytes": swap_used,
                    "freeBytes": 16 * (1024**3) - swap_used,
                },
                "gpu": {
                    "name": "NVIDIA GeForce RTX 4080",
                    "vendor": "NVIDIA",
                    "usagePercent": self.cur_gpu,
                    "memoryTotalBytes": 16 * (1024**3),
                    "memoryUsedBytes": int(self.cur_vram),
                    "temperatureC": self.cur_gpu_temp,
                },
                "disks": disks_payload,
                "network": {
                    "rxBytesPerSecond": self.cur_rx,
                    "txBytesPerSecond": self.cur_tx,
                },
            },
        }


class PcStatusClient(QObject):
    status_updated = pyqtSignal(dict)
    online_changed = pyqtSignal(bool)

    def __init__(self, mock_pc: bool = False, parent=None):
        super().__init__(parent)
        self.mock_pc = mock_pc
        self.mock_generator = MockPcMetricsGenerator()
        self.worker = None
        self._is_online = False
        self._last_received_ts = 0.0
        self._last_payload = None

        token = getattr(config, "PC_STATUS_TOKEN", "")
        port = getattr(config, "PC_STATUS_SERVER_PORT", getattr(config, "PORT", 3000))
        stale_after_ms = getattr(config, "PC_STATUS_STALE_AFTER_MS", 30000)
        self.server_thread = PcStatusServerThread(
            port=port, token=token, stale_after_ms=stale_after_ms, parent=self
        )
        self.server_thread.status_received.connect(self._on_direct_push)
        self.server_thread.start()

        self.timer = QTimer(self)
        self.timer.setInterval(config.PC_STATUS_REFRESH_MS)
        self.timer.timeout.connect(self._poll_status)
        self.timer.start()

    def _on_direct_push(self, payload: dict):
        if self.mock_pc:
            return

        if not payload.get("data") and not payload.get("Data"):
            normalized = {"online": True, "stale": False, "data": payload}
        else:
            normalized = {
                "online": True,
                "stale": False,
                "data": payload.get("data") or payload.get("Data"),
            }

        was_offline = not self._is_online
        self._last_received_ts = time.time()
        self._last_payload = normalized
        self._set_online(True)
        if was_offline:
            self.status_updated.emit(normalized)

    def set_mock_mode(self, enabled: bool):
        self.mock_pc = enabled
        if not enabled:
            self._set_online(False)
        self._poll_status()

    def toggle_mock_online(self):
        self.mock_pc = not self.mock_pc
        if not self.mock_pc:
            self._set_online(False)
        else:
            self._poll_status()

    def _set_online(self, online: bool):
        if self._is_online != online:
            self._is_online = online
            self.online_changed.emit(online)

    def _poll_status(self):
        if self.mock_pc:
            payload = self.mock_generator.get_payload()
            self._last_received_ts = time.time()
            self._last_payload = payload
            self._set_online(True)
            self.status_updated.emit(payload)
            return

        now = time.time()
        is_stale = (
            self._last_payload is None
            or (now - self._last_received_ts) > (config.PC_STATUS_STALE_AFTER_MS / 1000.0)
        )

        if is_stale:
            if self._is_online:
                self._set_online(False)
        else:
            self._set_online(True)
            if self._last_payload:
                self.status_updated.emit(self._last_payload)

        endpoint = getattr(config, "PC_STATUS_ENDPOINT", "")
        server_port = getattr(config, "PC_STATUS_SERVER_PORT", getattr(config, "PORT", 3000))
        is_internal_endpoint = f":{server_port}" in endpoint or "localhost" in endpoint or "127.0.0.1" in endpoint

        if endpoint and not is_internal_endpoint and (now - self._last_received_ts > 1.0):
            if not (self.worker and self.worker.isRunning()):
                token = getattr(config, "PC_STATUS_TOKEN", "")
                self.worker = PcStatusWorker(endpoint, token)
                self.worker.finished.connect(self._on_fetch_success)
                self.worker.failed.connect(self._on_fetch_failed)
                self.worker.start()

    def _on_fetch_success(self, payload: dict):
        online = payload.get("online", False) and bool(payload.get("data"))
        if online:
            was_offline = not self._is_online
            self._last_received_ts = time.time()
            self._last_payload = payload
            self._set_online(True)
            if was_offline:
                self.status_updated.emit(payload)
        else:
            if (time.time() - self._last_received_ts) > (config.PC_STATUS_STALE_AFTER_MS / 1000.0):
                self._set_online(False)

    def _on_fetch_failed(self, error_msg: str):
        if (time.time() - self._last_received_ts) > (config.PC_STATUS_STALE_AFTER_MS / 1000.0):
            self._set_online(False)
