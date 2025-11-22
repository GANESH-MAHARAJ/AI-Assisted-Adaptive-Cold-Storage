import json, re

from datetime import datetime, timezone

from typing import Tuple
from langchain_ollama import ChatOllama
from langchain.schema import HumanMessage, SystemMessage
from backend.models import AgentDecision, ActuatorCommand
from backend import config
# logger = logging.getLogger("agent")
# logger.setLevel(logging.INFO)


SYS_PROMPT = """You are a control policy agent for a closed-loop adaptive cold storage rack with two trays.
You will receive per-tray measurements: temperature (°C), humidity (%), CO2 (ppm), Ethylene (ppm), and weight (g).
Goal: Minimize energy while maintaining safe storage for fruits/veggies.
Rules:
- Output STRICT JSON with keys: {"actuators": {"rackACvalve":0|1, "rackHumidifiervalve":0|1, "tray1fanspeed":0-255, "tray2fanspeed":0-255}, "rationale": "short text"}.
- Prefer low fan speeds unless temperature/humidity/ethylene thresholds demand action.
- Open AC valve if any tray temp > target temp or CO2/Ethylene too high and airflow is needed.
- Open Humidifier valve if any tray humidity < target range and cooling airflow alone will not increase RH.
- If both flows are needed, both valves can be 1; fan speeds decide per-tray intensity.
- Keep responses compact. No code blocks, no prose outside JSON.
Targets (tune later):
- Temperature target 2-8°C (fruits/veg placeholder)
- Humidity target 80-95%
- CO2 keep below 5000 ppm; Ethylene keep below 10 ppm (placeholder safety).
"""

def _to_json_str(s: str) -> str:
    # try direct parse
    s = s.strip()
    try:
        json.loads(s)
        return s
    except:
        pass
    # extract largest { ... } block
    m = re.search(r"\{.*\}", s, flags=re.S)
    if m:
        return m.group(0)
    return "{}"

def decide(snapshot: dict) -> Tuple[AgentDecision, dict]:
    llm = ChatOllama(model=config.OLLAMA_MODEL, num_predict=config.AGENT_MAX_TOKENS)
    user = {
        "tray1": snapshot["tray1"],
        "tray2": snapshot["tray2"],
    }
    messages = [
        SystemMessage(content=SYS_PROMPT),
        HumanMessage(content=f"Measurements: {json.dumps(user, ensure_ascii=False)}"),
    ]
    raw = llm.invoke(messages).content
    json_text = _to_json_str(raw)
    try:
        data = json.loads(json_text)
    except:
        data = {"actuators": {"rackACvalve": 0, "rackHumidifiervalve": 0, "tray1fanspeed": 0, "tray2fanspeed": 0},
                "rationale": "fallback due to JSON parse error"}

    # clamp & validate
    act = data.get("actuators", {})
    cmd = ActuatorCommand(
        rackACvalve=int(bool(act.get("rackACvalve", 0))),
        rackHumidifiervalve=int(bool(act.get("rackHumidifiervalve", 0))),
        tray1fanspeed=max(0, min(255, int(act.get("tray1fanspeed", 0)))),
        tray2fanspeed=max(0, min(255, int(act.get("tray2fanspeed", 0)))),
    )
    decision = AgentDecision(actuators=cmd, rationale=str(data.get("rationale", "")))
    print(decision)
    return decision, {"raw": raw, "json_text": json_text}
