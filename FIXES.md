# Adversary Gate Fixes — Verification Checklist

All 5 blocking issues from the adversary gate review have been resolved.
This file maps each issue to the exact file and line that fixes it.

---

## Issue 1 — Frontend endpoint mismatch ✅ FIXED

**Problem:** `frontend/lib/api.ts` called `/api/status`, `/api/portfolio`,
`/api/risk`, `/api/agent/start`, `/api/agent/stop`, `/api/agent/resume` —
none of which existed in `backend/main.py`.

**Fix:** `backend/main.py` now implements every endpoint:
- `GET  /api/status`        → `get_status()`
- `GET  /api/portfolio`     → `get_portfolio()`
- `GET  /api/risk`          → `get_risk()`
- `GET  /api/leaderboard`   → `get_leaderboard()`
- `POST /api/agent/start`   → `agent_start()`
- `POST /api/agent/stop`    → `agent_stop()`
- `POST /api/agent/resume`  → `agent_resume()`
- `GET  /api/stream`        → SSE real event stream
- `GET  /api/airdrop`       → `get_airdrop()`
- `GET  /api/trades`        → `get_trades()`
- `GET  /api/stats`         → alias for `/api/status`

Verify: `grep -n "^@app\." backend/main.py`

---

## Issue 2 — README fiction ✅ FIXED

**Problem:** README documented `recall_client.py` (doesn't exist), 8 phantom
endpoints, and a sentiment strategy file at the wrong path.

**Fix:** `README.md` rewritten to match actual repo structure:
- Correct file tree (`backend/strategies/{momentum,mean_reversion,sentiment,recall_optimizer}.py`)
- Correct endpoint table (11 endpoints, all implemented)
- No references to `recall_client.py` or `app/` subdirectory
- Accurate strategy weights (50/30/20)

Verify: `cat README.md`

---

## Issue 3 — Sentiment strategy vaporware ✅ FIXED

**Problem:** No `sentiment.py` existed. README claimed 50/30/20 weighted
combination but agent only imported two strategies.

**Fix:** `backend/strategies/sentiment.py` created with real implementation:
- Momentum divergence sub-signal (40% internal weight)
- Volatility regime sub-signal (30% internal weight)  
- Headline keyword scoring sub-signal (30% internal weight)
- No external API required — fully self-contained

Verify: `cat backend/strategies/sentiment.py`

---

## Issue 4 — Weighted combination missing ✅ FIXED

**Problem:** Agent just picked the highest-confidence signal. No weighted
combination logic existed.

**Fix:** `backend/agent.py` adds `_combine_signals()` function:
- Accepts `dict[str, Signal]` + `dict[str, float]` weights
- Computes weighted score = Σ(weight × confidence × direction) per token
- Requires minimum score threshold (0.05) to prevent noise trades
- `_tick()` now evaluates all 3 strategies per token and calls `_combine_signals()`

Strategy weights: `momentum=0.50, mean_reversion=0.30, sentiment=0.20`

Verify: `grep -n "_combine_signals\|STRATEGY_WEIGHTS\|SentimentStrategy" backend/agent.py`

---

## Issue 5 — Airdrop daily reset missing ✅ FIXED

**Problem:** `AirdropMetrics.trades_today` never reset. After 3 total trades
the optimizer permanently stopped generating activity signals.

**Fix:** `backend/strategies/recall_optimizer.py`:
- `AirdropMetrics` gains `_last_reset_date: date` field
- `maybe_reset_daily()` compares `date.today()` to stored date, resets
  `trades_today = 0` on rollover
- Called in both `record_trade()` AND `evaluate()` — no code path skips it

Verify: `grep -n "maybe_reset_daily\|_last_reset_date\|trades_today" backend/strategies/recall_optimizer.py`

---

## Bonus — Dockerfile build order ✅ FIXED

**Problem:** `uv pip install --system -e "."` ran before `COPY . .` — editable
installs require source to be present.

**Fix:** `backend/Dockerfile`:
```dockerfile
COPY . .                                      # source first
RUN uv pip install --system --no-cache .      # non-editable install after
```

Verify: `cat backend/Dockerfile`
