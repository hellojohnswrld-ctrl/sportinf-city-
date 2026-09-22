import json, os
from datetime import datetime, timezone

PATH = "data/predictions.jsonl"

def log_prediction(payload: dict):
    os.makedirs("data", exist_ok=True)
    row = {"timestamp": datetime.now(timezone.utc).isoformat(), **payload}
    with open(PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
