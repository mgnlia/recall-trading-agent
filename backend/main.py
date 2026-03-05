"""
Recall AI Trading Agent — FastAPI Backend
"""

import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sse_starlette.sse import EventSourceResponse

from agent import agent


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Start background agent loop
    task = asyncio.create_task(agent.start())
    yield
    await agent.stop()
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


app = FastAPI(
    title="Recall AI Trading Agent",
    description="AI-powered trading agent with multi-strategy signals and RECALL airdrop farming",
    version="0.3.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Root + health
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "name": "Recall AI Trading Agent",
        "version": "0.3.0",
        "status": agent.state.status,
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# Agent state  (frontend calls /api/status)
# ---------------------------------------------------------------------------

@app.get("/api/status")
async def get_status():
    """Full agent state — used by dashboard status card."""
    s = agent.state
    return {
        "status": s.status,
        "portfolio_value": s.portfolio_value,
        "pnl": s.pnl,
        "pnl_pct": s.pnl_pct,
        "initial_value": s.initial_value,
        "airdrop_score": s.airdrop_score,
        "total_trades": s.total_trades,
        "last_update": s.last_update,
        "simulation_mode": True,
    }


# Legacy alias kept for backwards compat
@app.get("/api/stats")
async def get_stats():
    return await get_status()


# ---------------------------------------------------------------------------
# Portfolio  (frontend calls /api/portfolio)
# ---------------------------------------------------------------------------

@app.get("/api/portfolio")
async def get_portfolio():
    """Live portfolio snapshot."""
    portfolio = await agent.fetch_portfolio()
    return {
        **portfolio,
        "pnl": agent.state.pnl,
        "pnl_pct": agent.state.pnl_pct,
    }


# ---------------------------------------------------------------------------
# Trades  (frontend calls /api/trades)
# ---------------------------------------------------------------------------

@app.get("/api/trades")
async def get_trades(limit: int = 50):
    """Recent trade events."""
    trades = [
        e for e in reversed(agent.state.events)
        if e.get("type") == "trade"
    ][:limit]
    return {"trades": trades, "total": len(trades)}


# ---------------------------------------------------------------------------
# Risk  (frontend calls /api/risk)
# ---------------------------------------------------------------------------

@app.get("/api/risk")
async def get_risk():
    """Risk manager state."""
    r = agent.risk
    return {
        "halted": r.halted,
        "current_drawdown": round(r.current_drawdown * 100, 2),
        "peak_portfolio_value": r.peak_portfolio_value,
        "max_drawdown_pct": 15.0,
        "max_position_pct": 25.0,
        "total_trades_recorded": len(r.trade_history),
    }


# ---------------------------------------------------------------------------
# Airdrop  (frontend calls /api/airdrop)
# ---------------------------------------------------------------------------

@app.get("/api/airdrop")
async def get_airdrop():
    """RECALL airdrop farming progress."""
    m = agent.recall_opt.metrics
    return {
        "estimated_score": round(m.estimated_airdrop_score, 2),
        "activity_score": round(m.activity_score, 4),
        "total_trades": m.total_trades,
        "trades_today": m.trades_today,
        "unique_tokens_traded": len(m.unique_tokens_traded),
        "chains_used": list(m.chains_used),
    }


# ---------------------------------------------------------------------------
# Leaderboard  (frontend calls /api/leaderboard)
# ---------------------------------------------------------------------------

@app.get("/api/leaderboard")
async def get_leaderboard():
    """Competition leaderboard."""
    return await agent.fetch_leaderboard()


# ---------------------------------------------------------------------------
# Agent control  (frontend calls POST /api/agent/start|stop|resume)
# ---------------------------------------------------------------------------

@app.post("/api/agent/start")
async def agent_start():
    """Start the agent loop."""
    if agent.state.status == "running":
        return {"ok": False, "message": "Agent already running"}
    asyncio.create_task(agent.start())
    return {"ok": True, "message": "Agent starting"}


@app.post("/api/agent/stop")
async def agent_stop():
    """Stop the agent loop."""
    await agent.stop()
    return {"ok": True, "message": "Agent stopped"}


@app.post("/api/agent/resume")
async def agent_resume():
    """Resume after a risk halt."""
    await agent.resume()
    return {"ok": True, "message": "Agent resumed"}


# ---------------------------------------------------------------------------
# SSE stream  (frontend calls /api/stream)
# ---------------------------------------------------------------------------

@app.get("/api/stream")
async def stream_events():
    """SSE endpoint — streams agent events in real time."""

    async def event_generator():
        last_index = max(0, len(agent.state.events) - 1)
        while True:
            events = agent.state.events
            if len(events) > last_index:
                for event in events[last_index:]:
                    yield {"data": json.dumps(event)}
                last_index = len(events)
            else:
                yield {
                    "data": json.dumps({
                        "type": "heartbeat",
                        "data": {
                            "status": agent.state.status,
                            "portfolio_value": agent.state.portfolio_value,
                            "airdrop_score": agent.state.airdrop_score,
                        },
                    })
                }
            await asyncio.sleep(3)

    return EventSourceResponse(event_generator())
