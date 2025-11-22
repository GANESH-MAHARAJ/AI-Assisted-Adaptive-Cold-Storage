# backend/auto.py
import threading, time
from typing import Literal, Dict, Any
from backend.serial_reader import get_latest_snapshot
from backend.agent import decide as llm_decide
from backend.serial_writer import write_actuators_to_serial
from backend.db import log_event
from backend.models import ActuatorCommand
from backend import config
import json, time, threading

Mode = Literal["agent", "manual"]

_state_lock = threading.Lock()
_state: Dict[str, Any] = {
    "mode": "agent",            # "agent" or "manual"
    "ts": None,                 # ISO ts of last APPLY
    "snapshot": None,           # snapshot used for that APPLY
    "decision": None,           # {"actuators": {...}, "rationale": "..."}
    "debug": None,              # agent raw/debug or error
    "cycles": 0,                # number of apply cycles
}

_last_processed = None
_stop = False

def _baseline_decision(snap):
    # Simple safety rules as fallback
    T_LOW, T_HIGH = 2.0, 8.0
    RH_LOW, RH_HIGH = 85.0, 95.0
    CO2_MAX, ETH_MAX = 5000.0, 1000.0  # adjust to your sensor units
    t1,h1,c1,e1 = snap["tray1"]["temp"], snap["tray1"]["humidity"], snap["tray1"]["co2ppm"], snap["tray1"]["ethyleneppm"]
    t2,h2,c2,e2 = snap["tray2"]["temp"], snap["tray2"]["humidity"], snap["tray2"]["co2ppm"], snap["tray2"]["ethyleneppm"]
    need_ac  = (t1 > T_HIGH) or (t2 > T_HIGH) or (c1 > CO2_MAX) or (c2 > CO2_MAX) or (e1 > ETH_MAX) or (e2 > ETH_MAX)
    need_hum = (h1 < RH_LOW) or (h2 < RH_LOW)
    def pwm_for(temp, hum):
        base = 40
        t_boost = max(0, temp - T_HIGH) * 15
        h_boost = max(0, RH_LOW - hum) * 4
        return max(0, min(255, int(base + t_boost + h_boost)))
    cmd = {
        "rackACvalve": 1 if need_ac else 0,
        "rackHumidifiervalve": 1 if need_hum else 0,
        "tray1fanspeed": pwm_for(t1, h1),
        "tray2fanspeed": pwm_for(t2, h2),
    }
    return {"actuators": cmd, "rationale": "baseline rule (LLM unavailable or slow)"}

def set_mode(mode: Mode):
    with _state_lock:
        _state["mode"] = mode

def get_mode() -> Mode:
    with _state_lock:
        return _state["mode"]

def get_state() -> Dict[str, Any]:
    with _state_lock:
        # return a shallow copy to avoid races
        return dict(_state)

def _snap_changed(a, b, tol=0.01):  # 0.01 units is fine for temp/humidity
    if a is None or b is None:
        return True
    for tray in ("tray1","tray2"):
        for k in ("temp","humidity","co2ppm","ethyleneppm","weight"):
            if abs(a[tray][k] - b[tray][k]) > tol:
                return True
    return False

def _iso_utc_now():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()

def manual_apply(actuators: dict, snapshot: dict | None = None):
    """Immediate manual write + log + update state."""
    cmd = ActuatorCommand.model_validate(actuators).model_dump()
    snap = snapshot or get_latest_snapshot()
    write_actuators_to_serial(cmd)
    dec = {"actuators": cmd, "rationale": "manual/apply"}
    log_event(snap, dec)
    with _state_lock:
        _state.update({
            "ts": _iso_utc_now(),
            "snapshot": snap,
            "decision": dec,
            "debug": {"source": "manual"},
            "cycles": _state.get("cycles", 0) + 1,
        })
    return dec

def start_auto_loop(interval_s: float = 2.0, max_idle_s: float = 15.0):
    th = threading.Thread(target=_run, args=(interval_s, max_idle_s), daemon=True)
    th.start()
    return th

def _run(interval_s: float, max_idle_s: float):
    global _last_processed
    last_apply = 0.0
    while not _stop:
        try:
            if get_mode() == "agent":
                snap = get_latest_snapshot()

                # -------- DEBUG: print what we’re sending to the agent
                print("[AGENT-IN]", json.dumps(snap, separators=(',',':')))

                # only act if changed OR we've been idle too long
                if _snap_changed(snap, _last_processed) or (time.time()-last_apply > max_idle_s):
                    try:
                        decision, debug = llm_decide(snap)
                        dec_dict = {
                            "actuators": decision.actuators.model_dump(),
                            "rationale": decision.rationale
                        }
                        # -------- DEBUG: print agent raw + parsed
                        try:
                            raw = debug.get("raw") if isinstance(debug, dict) else None
                        except Exception:
                            raw = None
                        if raw:
                            print("[AGENT-RAW-OUT]", raw)
                        print("[AGENT-PARSED]", json.dumps(dec_dict, separators=(',',':')))
                    except Exception as e:
                        dec_dict = _baseline_decision(snap)
                        debug = {"error": f"agent_failed:{e.__class__.__name__}"}
                        print("[AGENT-ERROR]", repr(e))
                        print("[AGENT-FALLBACK]", json.dumps(dec_dict, separators=(',',':')))

                    # Apply to Arduino
                    cmd = dec_dict["actuators"]
                    print("[APPLY->SERIAL]", cmd)  # -------- DEBUG: what we write
                    write_actuators_to_serial(cmd)

                    # Log to Mongo
                    log_event(snap, dec_dict)

                    # Publish state
                    with _state_lock:
                        _state.update({
                            "ts": _iso_utc_now(),
                            "snapshot": snap,
                            "decision": dec_dict,
                            "debug": debug,
                            "cycles": _state.get("cycles", 0) + 1,
                        })
                    _last_processed = snap
                    last_apply = time.time()

            time.sleep(interval_s)
        except Exception as e:
            print("[AUTO-LOOP-ERROR]", repr(e))
            time.sleep(max(2.0, interval_s))
