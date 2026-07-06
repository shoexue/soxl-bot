from dataclasses import dataclass


@dataclass(frozen=True)
class FastStrategyConfig:
    symbol: str = "SOXL"
    regime_symbol: str = "QQQ"
    strategy_version: str = "fast_5d_zlt_m1_50_qqq_ma50_hold4_no_stop_v1"

    starting_capital: float = 10_000.0
    position_fraction: float = 0.50
    slippage: float = 0.001

    z_window: int = 5
    z_threshold: float = -1.50
    qqq_ma_window: int = 50
    hold_days: int = 4


FAST_STRATEGY_CONFIG = FastStrategyConfig()

