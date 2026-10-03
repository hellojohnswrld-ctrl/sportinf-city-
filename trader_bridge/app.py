import os
import time
import uuid
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="AI Liquidity Trader Bridge", version="2.0.0")
TOKEN = os.getenv("TRADER_BRIDGE_TOKEN", "")
LATEST: dict[str, dict[str, Any]] = {}
COMMANDS: dict[str, list[dict[str, Any]]] = {}

class StatePayload(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    timestamp: int
    state: str
    strength: int = 0
    chart: list[dict[str, Any]] = Field(default_factory=list)
    positions: list[dict[str, Any]] = Field(default_factory=list)
    model_config = {"extra": "allow"}

class CommandPayload(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    action: str = Field(min_length=1, max_length=40)
    value: str | None = None

def authorize(authorization: str | None):
    if not TOKEN:
        raise HTTPException(status_code=503, detail="bridge token is not configured")
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")

@app.get("/health")
def health():
    return {"ok": True, "service": "ai-liquidity-trader-bridge", "version": "2.0.0", "time": int(time.time()), "symbols": len(LATEST)}

@app.post("/v1/mt5/state")
def publish(payload: StatePayload, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = payload.model_dump()
    data["receivedAt"] = int(time.time())
    LATEST[payload.symbol.upper()] = data
    return {"ok": True, "symbol": payload.symbol.upper(), "receivedAt": data["receivedAt"]}

@app.get("/v1/mobile/state")
def mobile_state(symbol: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = LATEST.get(symbol.upper())
    if not data:
        raise HTTPException(status_code=404, detail="no live MT5 state for symbol")
    data = dict(data)
    data["stale"] = int(time.time()) - int(data.get("receivedAt", 0)) > 8
    return data

@app.get("/v1/mobile/symbols")
def mobile_symbols(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"symbols": sorted(LATEST.keys())}

@app.post("/v1/mobile/command")
def queue_command(payload: CommandPayload, authorization: str | None = Header(default=None)):
    authorize(authorization)
    allowed = {"ping", "close_all", "enable_trading", "disable_trading", "refresh"}
    action = payload.action.lower()
    if action not in allowed:
        raise HTTPException(status_code=400, detail=f"unsupported command: {action}")
    symbol = payload.symbol.upper()
    command = {"id": uuid.uuid4().hex, "action": action, "value": payload.value, "createdAt": int(time.time())}
    COMMANDS.setdefault(symbol, []).append(command)
    return {"ok": True, "command": command}

@app.get("/v1/mt5/commands")
def mt5_commands(symbol: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    key = symbol.upper()
    queue = COMMANDS.get(key, [])
    COMMANDS[key] = []
    return {"commands": queue}

@app.get("/v1/mobile/events")
def mobile_events(symbol: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = LATEST.get(symbol.upper())
    if not data:
        raise HTTPException(status_code=404, detail="no live MT5 state for symbol")
    return {
        "symbol": symbol.upper(),
        "timestamp": data.get("timestamp"),
        "state": data.get("state"),
        "strength": data.get("strength", 0),
        "forecastDirection": data.get("forecastDirection", "NEUTRAL"),
        "receivedAt": data.get("receivedAt", 0),
    }
