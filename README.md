# Recall AI Trading Agent 🤖

Multi-strategy AI trading agent for [Recall Network](https://recall.network) competitions. Competes for $25–30K prize pools per round while farming RECALL token airdrop rewards.

## Architecture

```
scanner → strategy → risk_manager → API client → trade
```

```
backend/app/
  recall_client.py     — Recall Competition API client (paper + spot)
  agent.py             — Main async agent loop
  risk.py              — Position sizing, drawdown halt, exposure limits
  config.py            — Pydantic settings from env vars
  main.py              — FastAPI: REST endpoints + SSE stream
  strategy/
    momentum.py        — Trend-following on price momentum
    mean_revert.py     — Z-score mean reversion
    sentiment.py       — News/social signal scanner
frontend/              — Next.js live dashboard (P&L, signals, trades, leaderboard)
```

## Strategies

| Strategy | Signal | Logic |
|---|---|---|
| **Momentum** | BUY/SELL | Price up >1.5% over window → BUY; down >1.5% → SELL |
| **Mean Reversion** | BUY/SELL | Z-score > 1.5 → oversold BUY; < -1.5 → overbought SELL |
| **Sentiment** | BUY/SELL | Keyword scan of crypto news headlines |

Signals are **weighted and combined** (momentum 50%, mean-revert 30%, sentiment 20%) before execution.

## Risk Management

- Max 25% portfolio in any single token
- Max 10% portfolio per trade
- Kelly-inspired signal-strength sizing
- Auto-halt if drawdown exceeds 10% from peak
- Day-rollover resets daily drawdown

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
uv run uvicorn app.main:app --reload --port 8000
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
| `RECALL_API_KEY` | *(required)* | Your Recall agent API key |
| `USE_SANDBOX` | `true` | Use sandbox for testing |
| `TRADE_INTERVAL_SECS` | `60` | Seconds between agent cycles |
| `MAX_POSITION_PCT` | `0.25` | Max % of portfolio per token |
| `MAX_TRADE_PCT` | `0.10` | Max % of portfolio per trade |
| `MAX_DAILY_DRAWDOWN_PCT` | `0.10` | Halt threshold |
| `MOMENTUM_WEIGHT` | `0.5` | Strategy weight |
| `MEAN_REVERT_WEIGHT` | `0.3` | Strategy weight |
| `SENTIMENT_WEIGHT` | `0.2` | Strategy weight |

### Frontend (`frontend/.env.local`)

| Variable | Default | Description |
|---|---|---|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend URL |

## API Endpoints

| Endpoint | Description |
|---|---|
| `GET /health` | Health check |
| `GET /api/status` | Full agent state |
| `GET /api/portfolio` | Live portfolio from Recall |
| `GET /api/trades` | Trade history |
| `GET /api/risk` | Risk manager state |
| `GET /api/leaderboard` | Competition leaderboard |
| `GET /api/stream` | SSE real-time stream |
| `POST /api/agent/start` | Start agent loop |
| `POST /api/agent/stop` | Stop agent loop |
| `POST /api/agent/resume` | Resume after halt |
| `POST /api/trade/manual` | Execute manual trade |

## Deployment

### Backend (Railway)

```bash
cd backend
railway up
```

Set env vars in Railway dashboard.

### Frontend (Vercel/Netlify)

```bash
cd frontend
vercel --prod
# Set NEXT_PUBLIC_API_URL to your Railway backend URL
```

## Competition Strategy

1. **Sandbox first** — verify API key works, watch signals for 1–2 cycles
2. **Switch to production** — set `USE_SANDBOX=false` before competition starts
3. **Monitor dashboard** — watch drawdown, halt reason, leaderboard rank
4. **Boost farming** — stake RECALL to boost your own agent for compounding rewards

## Tokens Tracked

WETH, WBTC, LINK, UNI, AAVE (all EVM/Ethereum mainnet fork addresses)

## Links

- [Recall Docs](https://docs.recall.network)
- [Python Quickstart](https://docs.recall.network/competitions/build-agent/your-first-trade)
- [Paper Trading API](https://docs.recall.network/competitions/build-agent/trading)
- [Competition App](https://competitions.recall.network)
