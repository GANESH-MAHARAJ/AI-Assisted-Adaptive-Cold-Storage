from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

from datetime import datetime, timezone


from backend.serial_reader import start_reader, get_latest_snapshot
from backend.serial_writer import write_actuators_to_serial
from backend.agent import decide
from backend.db import log_event, latest_n
from backend.models import RackSnapshot, AgentDecision, ActuatorCommand

import os, os.path
from backend.auto import start_auto_loop, get_state, set_mode, get_mode, manual_apply

app = Flask(__name__)
CORS(app)

# start serial reader ONLY in the main process (to avoid double threads under debug)
if os.environ.get("WERKZEUG_RUN_MAIN") == "true" or not app.debug:
    start_reader()
    start_auto_loop(interval_s=2.0, max_idle_s=15)  # poll/act every 5s after new data


@app.get("/sensors/live")
def sensors_live():
    """Return last known snapshot (tray1/tray2)."""
    snap = get_latest_snapshot()
    
    return jsonify({"ts": datetime.now(timezone.utc).isoformat(), "snapshot": snap})


@app.post("/agent/decide")
def agent_decide():
    """
    Optional body: { "snapshot": {...} }  # if omitted, uses live snapshot
    Returns: { "decision": {...}, "debug": {...} }
    """
    payload = request.get_json(silent=True) or {}
    snap = payload.get("snapshot") or get_latest_snapshot()
    # validate minimal shape
    RackSnapshot.model_validate(snap)

    decision, debug = decide(snap)
    dec_dict = {
        "actuators": decision.actuators.model_dump(),
        "rationale": decision.rationale
    }
    # log (sensors + decision)
    log_event(snap, dec_dict)
    return jsonify({"decision": dec_dict, "debug": debug})

@app.post("/actuators/apply")
def actuators_apply():
    """
    Body: {"actuators": {"rackACvalve":0|1,"rackHumidifiervalve":0|1,"tray1fanspeed":0-255,"tray2fanspeed":0-255},
           "snapshot": {...}
    }
    Writes to Arduino immediately & logs to Mongo.
    """
    payload = request.get_json(force=True)
    act = payload.get("actuators")
    if not act:
        return jsonify({"error": "missing actuators"}), 400

    cmd = ActuatorCommand.model_validate(act).model_dump()
    write_actuators_to_serial(cmd)

    snap = payload.get("snapshot") or get_latest_snapshot()
    RackSnapshot.model_validate(snap)
    log_event(snap, {"actuators": cmd, "rationale": "manual/apply"})

    return jsonify({"status": "ok", "applied": cmd})

@app.get("/plots/latest")
def plots_latest():
    """
    Returns last N records (default 200) for client plotting.
    """
    n = int(request.args.get("n", "200"))
    docs = latest_n(n)
    # convert datetime to iso
    for d in docs:
        d["ts"] = d["ts"].isoformat() + "Z"
    return jsonify({"items": docs})

# serve dashboard file for convenience
@app.get("/")
def root():
    return send_from_directory("../dashboard", "index.html")


@app.get("/health")
def health():
    status = {"serial":"unknown", "mongo":"unknown", "ollama":"unknown"}

    # serial data present?
    from backend.serial_reader import get_latest_snapshot
    snap = get_latest_snapshot()
    all_zeroish = all(abs(v) < 1e-9 for t in snap.values() for v in t.values())
    status["serial"] = "ok" if not all_zeroish else "no-data"

    # mongo reachable?
    try:
        from backend.db import latest_n
        _ = latest_n(1)
        status["mongo"] = "ok"
    except Exception as e:
        status["mongo"] = f"error: {e.__class__.__name__}"

    # ollama import presence (lightweight check)
    try:
        import langchain_ollama  # noqa
        status["ollama"] = "installed"
    except Exception as e:
        status["ollama"] = f"error: {e.__class__.__name__}"

    return jsonify(status)

@app.get("/debug/snapshot")
def debug_snapshot():
    from backend.serial_reader import get_latest_snapshot
    return jsonify(get_latest_snapshot())

@app.get("/state")
def state():
    """Return the latest applied cycle: snapshot + decision + ts + mode."""
    s = get_state()
    s["mode"] = get_mode()
    return jsonify(s)

@app.post("/mode")
def mode_set():
    body = request.get_json(force=True)
    mode = body.get("mode")
    if mode not in ("agent","manual"):
        return jsonify({"error":"mode must be 'agent' or 'manual'"}), 400
    set_mode(mode)
    return jsonify({"ok": True, "mode": mode})

@app.post("/manual/apply")
def manual_apply_route():
    body = request.get_json(force=True)
    act = body.get("actuators")
    if not act:
        return jsonify({"error":"missing actuators"}), 400
    snap = body.get("snapshot")  # optional
    dec = manual_apply(act, snap)
    return jsonify({"applied": dec})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True, use_reloader=False)
