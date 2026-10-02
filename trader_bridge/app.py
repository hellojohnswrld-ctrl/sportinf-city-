import os
import time
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="AI Liquidity Trader Bridge", version="1.0.0")
TOKEN = os.getenv("TRADER_BRIDGE_TOKEN", "")
LATEST: dict[str, dict[str, Any]] = {}

class StatePayload(BaseModel):
    symbol: str = Field(min_length=1, max_length=40)
    timestamp: int
    state: str
    strength: int = 0
    chart: list[dict[str, float | int]] = []
    model_config = {"extra": "allow"}

def authorize(authorization: str | None):
    if not TOKEN:
        raise HTTPException(status_code=503, detail="bridge token is not configured")
    if authorization != f"Bearer {TOKEN}":
        raise HTTPException(status_code=401, detail="unauthorized")

@app.get("/health")
def health():
    return {"ok": True, "service": "ai-liquidity-trader-bridge", "time": int(time.time())}

@app.post("/v1/mt5/state")
def publish(payload: StatePayload, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = payload.model_dump()
    data["receivedAt"] = int(time.time())
    LATEST[payload.symbol.upper()] = data
    return {"ok": True, "symbol": payload.symbol, "receivedAt": data["receivedAt"]}

@app.get("/v1/mobile/state")
def mobile_state(symbol: str, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = LATEST.get(symbol.upper())
    if not data:
        raise HTTPException(status_code=404, detail="no live MT5 state for symbol")
    return data

@app.get("/v1/mobile/symbols")
def mobile_symbols(authorization: str | None = Header(default=None)):
    authorize(authorization)
    return {"symbols": sorted(LATEST.keys())}
