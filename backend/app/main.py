"""
FastAPI server — REST endpoints + SSE stream for dashboard.
"""
import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

import structlog
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from app.agent import agent
from app.config import settings

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    await agent.start()
    yield
    await agent.stop()


app = FastAPI(
    title="Recall AI Trading Agent",
    description="Multi-strategy AI agent for Recall Network competitions",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health ───────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "sandbox": settings.use_sandbox,
        "agent": settings.agent_name,
    }


# ── Portfolio ────────────────────────────────────────────────────────────────

@app.get("/api/portfolio")
async def get_portfolio():
    """Live portfolio from Recall API."""
    if not agent.client.has_credentials:
        raise HTTPException(status_code=503, detail="No API key configured")
    portfolio = await agent.client.get_portfolio()
    return {
        "agent_id": portfolio.agent_id,
        "total_value": portfolio.total_value,
        "tokens": [
            {
                "symbol": t.symbol,
                "amount": t.amount,
                "price": t.price,
                "value": t.value,
            }
            for t in portfolio.tokens
        ],
        "snapshot_time": portfolio.snapshot_time,
    }


# ── Leaderboard ──────────────────────────────────────────────────────────────

@app.get("/api/leaderboard")
async def get_leaderboard():
    if not agent.client.has_credentials:
        raise HTTPException(status_code=503, detail="No API key configured")
    return await agent.client.get_leaderboard()


# ── Agent status ─────────────────────────────────────────────────────────────

@app.get("/api/status")
async def get_status():
    return agent.get_status()


@app.get("/api/trades")
async def get_trades(limit: int = Query(50, le=200)):
    return {
        "trades": agent.trade_history[-limit:],
        "total": len(agent.trade_history),
    }


@app.get("/api/risk")
async def get_risk():
    return agent.risk.to_dict()


# ── Manual controls ──────────────────────────────────────────────────────────

@app.post("/api/agent/start")
async def start_agent():
    if not agent.running:
        await agent.start()
    return {"running": agent.running}


@app.post("/api/agent/stop")
async def stop_agent():
    await agent.stop()
    return {"running": agent.running}


@app.post("/api/agent/resume")
async def resume_agent():
    agent.risk.resume()
    return {"halted": agent.risk.is_halted}


class ManualTradeRequest(BaseModel):
    from_token: str
    to_token: str
    amount: float
    reason: str = "Manual trade"


@app.post("/api/trade/manual")
async def manual_trade(req: ManualTradeRequest):
    """Execute a manual trade (for testing/override)."""
    if not agent.client.has_credentials:
        raise HTTPException(status_code=503, detail="No API key configured")
    result = await agent.client.execute_trade(
        from_token=req.from_token,
        to_token=req.to_token,
        amount=req.amount,
        reason=req.reason,
    )
    return {
        "success": result.success,
        "tx_id": result.transaction_id,
        "error": result.error,
    }


# ── SSE Stream ───────────────────────────────────────────────────────────────

@app.get("/api/stream")
async def sse_stream():
    """Server-Sent Events stream — real-time agent state to dashboard."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=50)
    agent.sse_subscribers.append(queue)

    async def event_generator():
        try:
            # Send current state immediately on connect
            current = agent.get_status()
            yield f"data: {json.dumps(current)}\n\n"

            while True:
                try:
                    data = await asyncio.wait_for(queue.get(), timeout=30)
                    yield f"data: {json.dumps(data)}\n\n"
                except asyncio.TimeoutError:
                    # Keepalive ping
                    yield ": ping\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            if queue in agent.sse_subscribers:
                agent.sse_subscribers.remove(queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
