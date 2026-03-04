"""FastAPI application — dashboard API + SSE stream."""

from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from agent import agent
from config import settings

logging.basicConfig(level=settings.log_level.upper(), format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[no-untyped-def]
    """Start agent on boot, stop on shutdown."""
    task = asyncio.create_task(agent.start())
    yield
    await agent.stop()
    task.cancel()


app = FastAPI(title="Recall Trading Agent", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# REST endpoints
# ---------------------------------------------------------------------------


@app.get("/api/stats")
async def get_stats():
    """Current agent stats."""
    s = agent.state
    return {
        "status": s.status,
        "portfolioValue": s.portfolio_value,
        "pnl": s.pnl,
        "pnlPct": s.pnl_pct,
        "initialValue": s.initial_value,
        "totalTrades": s.total_trades,
        "airdropScore": s.airdrop_score,
        "lastUpdate": s.last_update,
        "simulationMode": settings.simulation_mode,
        "riskHalted": agent.risk.halted,
        "drawdown": agent.risk.current_drawdown,
    }


@app.get("/api/trades")
async def get_trades():
    """Trade history."""
    return {"trades": agent.risk.trade_history[-100:]}


@app.get("/api/airdrop")
async def get_airdrop():
    """Airdrop farming metrics."""
    m = agent.recall_opt.metrics
    return {
        "estimatedScore": m.estimated_airdrop_score,
        "activityScore": m.activity_score,
        "totalTrades": m.total_trades,
        "tradesToday": m.trades_today,
        "uniqueTokens": len(m.unique_tokens_traded),
        "chainsUsed": list(m.chains_used),
    }


@app.get("/api/events")
async def get_events():
    """Recent event log."""
    return {"events": agent.state.events[-50:]}


@app.get("/api/stream")
async def stream_events():
    """SSE endpoint for live dashboard updates."""

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        last_idx = len(agent.state.events)
        while True:
            await asyncio.sleep(2)
            current = agent.state.events
            if len(current) > last_idx:
                for ev in current[last_idx:]:
                    yield {"event": ev.get("type", "tick"), "data": json.dumps(ev)}
                last_idx = len(current)
            # Always send heartbeat with stats
            s = agent.state
            yield {
                "event": "stats",
                "data": json.dumps({
                    "portfolioValue": s.portfolio_value,
                    "pnl": s.pnl,
                    "pnlPct": s.pnl_pct,
                    "airdropScore": s.airdrop_score,
                    "totalTrades": s.total_trades,
                    "status": s.status,
                }),
            }

    return EventSourceResponse(event_generator())


@app.get("/health")
async def health():
    return {"status": "ok", "agent": agent.state.status}


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=True)
