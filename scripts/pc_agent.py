import ctypes
import json
import os
import subprocess
import sys
import time
from urllib.request import Request, urlopen

try:
    import psutil
except ImportError:
    psutil = None


def load_env():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".env")
    if not os.path.exists(env_path):
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ[k.strip()] = v.strip().strip('"').strip("'")


load_env()

_default_port = os.getenv("PC_STATUS_SERVER_PORT", os.getenv("PORT", "3000"))
_default_host = os.getenv("PC_STATUS_HOST", "localhost")
ENDPOINT = os.getenv("PC_STATUS_ENDPOINT", f"http://{_default_host}:{_default_port}/api/pc-status")
TOKEN = os.getenv("PC_STATUS_TOKEN", "change-me")
INTERVAL_MS = int(os.getenv("PC_STATUS_INTERVAL_MS", "1000"))


def get_boot_uptime() -> int:
    if sys.platform == "win32":
        return int(ctypes.windll.kernel32.GetTickCount64() / 1000.0)
    if psutil is not None:
        return int(time.time() - psutil.boot_time())
    return 0


def get_disks() -> list[dict]:
    disks = []
    if sys.platform == "win32":
        try:
            buf = ctypes.create_unicode_buffer(2048)
            n = ctypes.windll.kernel32.GetLogicalDriveStringsW(ctypes.sizeof(buf), buf)
            drives = [d for d in buf[:n].split("\x00") if d]
            for d in drives:
                if ctypes.windll.kernel32.GetDriveTypeW(d) == 3:
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
                            "usagePercent": 0.0,
                        })
        except Exception:
            pass
    elif psutil is not None:
        try:
            for p in psutil.disk_partitions(all=False):
                if "cdrom" in p.opts or p.fstype in ("nfs", "cifs", "smbfs", ""):
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
                            "usagePercent": 0.0,
                        })
                except Exception:
                    continue
        except Exception:
            pass
    return disks


def get_gpu_status() -> dict:
    try:
        startupinfo = None
        if sys.platform == "win32":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0

        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.total,memory.used,temperature.gpu",
                "--format=csv,noheader,nounits",
            ],
            text=True,
            startupinfo=startupinfo,
            timeout=1.5,
        ).strip()

        if out:
            line = out.split("\n")[0]
            parts = [p.strip() for p in line.split(",")]
            if len(parts) >= 5:
                name = parts[0]
                usage_pct = float(parts[1])
                total_mb = float(parts[2])
                used_mb = float(parts[3])
                temp_c = float(parts[4])
                return {
                    "name": name,
                    "vendor": "NVIDIA",
                    "usagePercent": usage_pct,
                    "memoryTotalBytes": int(total_mb * 1024 * 1024),
                    "memoryUsedBytes": int(used_mb * 1024 * 1024),
                    "temperatureC": temp_c,
                }
    except Exception:
        pass

    return {
        "name": "GPU",
        "vendor": "",
        "usagePercent": 0.0,
        "memoryTotalBytes": 0,
        "memoryUsedBytes": 0,
        "temperatureC": None,
    }


def main():
    print(f"[PC Agent] Отправка метрик на {ENDPOINT} каждые {INTERVAL_MS} мс...")
    last_net_bytes = None
    last_net_time = None
    last_disk_io = {}
    last_disk_time = 0.0

    while True:
        try:
            now = time.time()
            uptime_sec = get_boot_uptime()

            cpu_pct = 0.0
            vm_total = 0
            vm_used = 0
            swap_used = 0
            swap_total = 0
            rx_rate = 0
            tx_rate = 0

            if psutil is not None:
                cpu_pct = psutil.cpu_percent(interval=None)
                vm = psutil.virtual_memory()
                vm_total = vm.total
                vm_used = vm.used
                swap = psutil.swap_memory()
                swap_used = swap.used
                swap_total = swap.total

                cur_net = psutil.net_io_counters()
                if last_net_bytes is not None and last_net_time is not None:
                    dt = max(now - last_net_time, 0.001)
                    tx_rate = max(0, int((cur_net.bytes_sent - last_net_bytes[0]) / dt))
                    rx_rate = max(0, int((cur_net.bytes_recv - last_net_bytes[1]) / dt))
                last_net_bytes = (cur_net.bytes_sent, cur_net.bytes_recv)
                last_net_time = now

            disks = get_disks()
            if psutil is not None:
                per_io = psutil.disk_io_counters(perdisk=True) or {}
                dt_disk = max(now - last_disk_time, 0.001) if last_disk_time > 0 else 1.0
                new_disk_io = {}
                for disk in disks:
                    d_key = disk["label"].replace(":", "").lower()
                    io_now = None
                    for k, v in per_io.items():
                        if d_key in k.lower():
                            io_now = v
                            break
                    if io_now:
                        new_disk_io[disk["label"]] = (io_now.read_time, io_now.write_time)
                        if disk["label"] in last_disk_io:
                            old_rt, old_wt = last_disk_io[disk["label"]]
                            delta_busy_ms = (io_now.read_time - old_rt) + (io_now.write_time - old_wt)
                            disk["usagePercent"] = round(
                                min(100.0, max(0.0, (delta_busy_ms / (dt_disk * 1000.0)) * 100.0)), 1
                            )
                last_disk_io = new_disk_io
                last_disk_time = now

            gpu_status = get_gpu_status()

            payload = {
                "online": True,
                "stale": False,
                "updatedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                "data": {
                    "host": os.environ.get("COMPUTERNAME", "PC"),
                    "uptimeSeconds": uptime_sec,
                    "cpu": {
                        "usagePercent": cpu_pct,
                    },
                    "memory": {
                        "totalBytes": vm_total,
                        "usedBytes": vm_used,
                        "freeBytes": max(0, vm_total - vm_used),
                        "commitUsedBytes": vm_used + swap_used,
                    },
                    "swap": {
                        "totalBytes": swap_total,
                        "usedBytes": swap_used,
                        "freeBytes": max(0, swap_total - swap_used),
                    },
                    "gpu": gpu_status,
                    "disks": disks,
                    "network": {
                        "rxBytesPerSecond": rx_rate,
                        "txBytesPerSecond": tx_rate,
                    },
                },
            }

            data_bytes = json.dumps(payload).encode("utf-8")
            req = Request(ENDPOINT, data=data_bytes, method="POST")
            req.add_header("Content-Type", "application/json")
            if TOKEN:
                req.add_header("Authorization", f"Bearer {TOKEN}")

            with urlopen(req, timeout=2) as resp:
                if resp.status != 200:
                    print(f"[PC Agent] Ошибка ответа сервера: HTTP {resp.status}")

        except Exception as e:
            print(f"[PC Agent] Не удалось отправить статус: {e}")

        time.sleep(INTERVAL_MS / 1000.0)


if __name__ == "__main__":
    main()
