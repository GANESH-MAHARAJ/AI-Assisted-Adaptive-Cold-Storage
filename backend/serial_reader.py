import threading, time, serial
from backend import config
import re

NUM_RE = re.compile(r'[-+]?\d*\.\d+|[-+]?\d+')

# Global serial handle
_ser = None

_latest_lock = threading.Lock()
_latest_snapshot = {
    "tray1": {"temp": 0.0, "humidity": 0.0, "co2ppm": 0.0, "ethyleneppm": 0.0, "weight": 0.0},
    "tray2": {"temp": 0.0, "humidity": 0.0, "co2ppm": 0.0, "ethyleneppm": 0.0, "weight": 0.0},
}

def _parse_line(line: str):
    nums = [float(x) for x in NUM_RE.findall(line)]
    if len(nums) != 10:
        print("[PARSE-REJECT] got", len(nums), "numbers:", line)
        return None
    t1, h1, c1, e1, w1, t2, h2, c2, e2, w2 = nums
    if w1 < 0: w1 = 0.0
    if w2 < 0: w2 = 0.0
    return {
        "tray1": {"temp": t1, "humidity": h1, "co2ppm": c1, "ethyleneppm": e1, "weight": w1},
        "tray2": {"temp": t2, "humidity": h2, "co2ppm": c2, "ethyleneppm": e2, "weight": w2},
    }

def get_latest_snapshot():
    with _latest_lock:
        return {k: v.copy() for k, v in _latest_snapshot.items()}

def get_serial_handle():
    """Return the global serial handle (opened by start_reader)."""
    return _ser

def start_reader():
    th = threading.Thread(target=_run, daemon=True)
    th.start()
    return th

def _run():
    global _ser
    while True:
        try:
            if _ser is None or not _ser.is_open:
                print(f"[SERIAL] Opening {config.SERIAL_PORT} at {config.SERIAL_BAUD}…")
                _ser = serial.Serial(config.SERIAL_PORT, config.SERIAL_BAUD, timeout=2)

            line = _ser.readline().decode(errors="ignore").strip()
            if line:
                print("[SERIAL]", line)
                snap = _parse_line(line)
                if snap:
                    print("[PARSED]", snap)
                    with _latest_lock:
                        _latest_snapshot.update(snap)
            else:
                time.sleep(config.SERIAL_READ_INTERVAL_MS/1000.0)

        except Exception as e:
            print("[SERIAL-ERROR]", e)
            if _ser:
                try:
                    _ser.close()
                except Exception:
                    pass
                _ser = None
            time.sleep(2)
