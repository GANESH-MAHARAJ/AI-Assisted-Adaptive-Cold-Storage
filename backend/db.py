from pymongo import MongoClient
from datetime import datetime, timezone

from backend import config


_client = MongoClient(config.MONGO_URI)
_db = _client[config.MONGO_DB]
_col = _db[config.MONGO_COLLECTION]

def log_event(snapshot: dict, decision: dict):
    doc = {
        "ts": datetime.utcnow(),
        "sensors": snapshot,     # dict with tray1/tray2
        "decision": decision     # dict with actuators + rationale
    }
    _col.insert_one(doc)

def latest_n(n=200):
    cur = _col.find({}, {"_id": 0}).sort("ts", -1).limit(n)
    return list(cur)[::-1]
