# Recall AI Trading Agent 🤖

Multi-strategy AI trading agent for [Recall Network](https://recall.network) competitions. Competes for $25–30K prize pools per round while farming RECALL token airdrop rewards.

## Architecture

```
price feed → strategies → weighted combiner → risk manager → trade executor
```

```
backend/
  main.py              — FastAPI: REST endpoints + SSE stream
  agent.py             — Main async agent loop + weighted signal combiner
  risk.py              — Position sizing, drawdown halt, exposure limits
  config.py            — Pydantic settings from env vars
  strategies/
    momentum.py        — Trend-following on short vs long price momentum
    mean_reversion.py  — Z-score mean reversion (window=20, z_threshold=1.5)
    sentiment.py       — Synthetic sentiment: momentum divergence + volatility regime + headline keywords
    recall_optimizer.py — Airdrop score optimizer (diversity + activity signals)
frontend/              — Next.js 14 live dashboard (P&L, signals, trades, leaderboard)
```

## Strategies

| Strategy | Weight | Signal Logic |
|---|---|---|
| **Momentum** | 50% | Short-window return > 2% threshold → BUY/SELL |
| **Mean Reversion** | 30% | Z-score > 1.5 std dev from 20-period mean → BUY/SELL |
| **Sentiment** | 20% | Momentum divergence (40%) + volatility regime (30%) + headline keywords (30%) |

Signals are **weighted and combined** per token before execution. The combined confidence score must exceed a minimum threshold (0.05) to trigger a trade.

## Risk Management

- Max 25% portfolio in any single token
- Kelly-inspired sizing: trade size = max_position × confidence
- Auto-halt if drawdown exceeds 15% from peak
- `POST /api/agent/resume` to clear halt and restart

## Quick Start

### 1. Register on Recall

1. Go to [competitions.recall.network](https://competitions.recall.network)
2. Create a profile → create an agent → get your API key
3. Register your agent for an active competition

### 2. Backend

```bash
cd backend
cp .env.example .env
# Edit .env: set RECALL_API_KEY

uv sync
uv run python main.py
```

### 3. Frontend

```bash
cd frontend
npm install
# Set NEXT_PUBLIC_API_URL=http://localhost:8000 in .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000)

## Environment Variables

### Backend (`backend/.env`)

| Variable | Default | Description |
|---|---|---|
| `RECALL_API_KEY` | `demo_key` | Your Recall agent API key |
| `RECALL_BASE_URL` | sandbox URL | Recall API base URL |
| `SIMULATION_MODE` | `true` | Use simulated prices/trades |
| `TRADE_INTERVAL_SECONDS` | `60` | Seconds between agent cycles |
| `MAX_POSITION_PCT` | `0.25` | Max % of portfolio per token |
| `MAX_DRAWDOWN_PCT` | `0.15` | Halt threshold |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL |

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `GET /api/status` | Full agent state (status, PnL, airdrop score) |
| `GET /api/portfolio` | Live portfolio snapshot |
| `GET /api/trades` | Trade event history |
| `GET /api/risk` | Risk manager state (drawdown, halt) |
| `GET /api/airdrop` | RECALL airdrop farming progress |
| `GET /api/leaderboard` | Competition leaderboard |
| `GET /api/stream` | SSE real-time event stream |
| `POST /api/agent/start` | Start agent loop |
| `POST /api/agent/stop` | Stop agent loop |
| `POST /api/agent/resume` | Resume after risk halt |

## Deployment

### Backend (Railway)

Connect the `backend/` directory as a Railway service — `railway.toml` is pre-configured with Dockerfile builder and `/health` check.

### Frontend (Railway / Vercel)

Connect the `frontend/` directory — `railway.toml` uses Nixpacks + `npm run build`. Set `NEXT_PUBLIC_API_URL` to your backend URL.

## Airdrop Farming

The `RecallOptimizer` tracks daily trading activity and generates diversification signals when the agent is idle:
- Encourages at least 3 trades/day for activity score
- Targets tokens not yet traded for diversity score
- Daily counter resets at midnight automatically

## Links

- [Recall Docs](https://docs.recall.network)
- [Competition App](https://competitions.recall.network)
- [Trading API](https://docs.recall.network/competitions/build-agent/trading)
