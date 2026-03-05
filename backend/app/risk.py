"""
Risk Manager — position sizing, drawdown protection, exposure limits.

Enforces:
- Max position size per token (% of portfolio)
- Max trade size (% of portfolio)
- Max daily drawdown (halt if portfolio drops too far from peak)
- Min trade size (avoid dust trades)
"""
import structlog
from dataclasses import dataclass, field
from datetime import date

from app.config import settings

logger = structlog.get_logger(__name__)


@dataclass
class RiskState:
    peak_value: float = 0.0
    current_value: float = 0.0
    daily_start_value: float = 0.0
    date: str = field(default_factory=lambda: str(date.today()))
    halted: bool = False
    halt_reason: str = ""
    trade_count_today: int = 0
    total_trades: int = 0


class RiskManager:
    """
    Enforces risk limits before every trade decision.
    """

    def __init__(self):
        self.state = RiskState()

    def update_portfolio_value(self, total_value: float):
        """Called after each portfolio refresh."""
        today = str(date.today())

        # Day rollover
        if self.state.date != today:
            logger.info(
                "risk.day_reset",
                old_date=self.state.date,
                new_date=today,
                prev_value=self.state.current_value,
            )
            self.state.date = today
            self.state.daily_start_value = total_value
            self.state.trade_count_today = 0
            # Resume if halted (new day = fresh start)
            if self.state.halted:
                self.state.halted = False
                self.state.halt_reason = ""

        # First update of the day
        if self.state.daily_start_value == 0:
            self.state.daily_start_value = total_value

        self.state.current_value = total_value

        # Update peak (high-water mark)
        if total_value > self.state.peak_value:
            self.state.peak_value = total_value

        # Check drawdown from peak
        if self.state.peak_value > 0:
            drawdown = (
                (self.state.peak_value - total_value) / self.state.peak_value
            )
            if drawdown >= settings.max_daily_drawdown_pct:
                self.halt(
                    f"Max drawdown exceeded: {drawdown:.1%} from peak "
                    f"(peak={self.state.peak_value:.2f}, "
                    f"current={total_value:.2f})"
                )

    def size_trade(
        self,
        portfolio_value: float,
        from_token_value: float,
        signal_strength: float,
    ) -> float:
        """
        Calculate trade size in USD.

        Uses Kelly-inspired sizing: scale by signal strength within limits.
        Returns 0 if trade should not be placed.
        """
        if self.state.halted:
            return 0.0

        # Base size = max_trade_pct of portfolio, scaled by signal
        max_trade_usd = portfolio_value * settings.max_trade_pct
        trade_usd = max_trade_usd * signal_strength

        # Never exceed available balance
        trade_usd = min(trade_usd, from_token_value * 0.99)

        # Enforce minimum
        if trade_usd < settings.min_trade_usd:
            return 0.0

        return trade_usd

    def check_position(
        self,
        portfolio_value: float,
        token_current_value: float,
        proposed_buy_usd: float,
    ) -> tuple[bool, str]:
        """
        Check if buying would exceed max position size.
        Returns (allowed, reason).
        """
        if self.state.halted:
            return False, f"Trading halted: {self.state.halt_reason}"

        new_position_value = token_current_value + proposed_buy_usd
        position_pct = (
            new_position_value / portfolio_value
            if portfolio_value > 0
            else 1.0
        )

        if position_pct > settings.max_position_pct:
            return False, (
                f"Position limit: {position_pct:.1%} would exceed "
                f"max {settings.max_position_pct:.1%}"
            )

        return True, "ok"

    def record_trade(self):
        """Track trade counts."""
        self.state.trade_count_today += 1
        self.state.total_trades += 1

    def halt(self, reason: str):
        """Emergency halt — stop all trading."""
        if not self.state.halted:
            self.state.halted = True
            self.state.halt_reason = reason
            logger.critical("risk.HALT", reason=reason)

    def resume(self):
        """Manual resume after halt."""
        self.state.halted = False
        self.state.halt_reason = ""
        logger.info("risk.resume")

    @property
    def is_halted(self) -> bool:
        return self.state.halted

    def to_dict(self) -> dict:
        pnl = self.state.current_value - self.state.daily_start_value
        pnl_pct = (
            pnl / self.state.daily_start_value
            if self.state.daily_start_value > 0
            else 0
        )
        drawdown = 0.0
        if self.state.peak_value > 0:
            drawdown = (
                (self.state.peak_value - self.state.current_value)
                / self.state.peak_value
            )

        return {
            "halted": self.state.halted,
            "halt_reason": self.state.halt_reason,
            "current_value": round(self.state.current_value, 2),
            "peak_value": round(self.state.peak_value, 2),
            "daily_start_value": round(self.state.daily_start_value, 2),
            "daily_pnl": round(pnl, 2),
            "daily_pnl_pct": round(pnl_pct * 100, 2),
            "drawdown_from_peak_pct": round(drawdown * 100, 2),
            "trade_count_today": self.state.trade_count_today,
            "total_trades": self.state.total_trades,
            "date": self.state.date,
        }
