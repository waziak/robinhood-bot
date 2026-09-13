"""Transaction friction. Fills never happen at the midpoint.

Assumptions (per side, basis points of price). They are deliberately conservative for a retail Robinhood account
and are stress-tested at 2x and 3x in every report:
- Index ETFs (SPY/QQQ/IWM/DIA): half-spread 0.5 bp + slippage 2 bp
- Sector/bond/gold ETFs, mega-cap stocks: half-spread 1 bp + slippage 3 bp
- Crypto via Robinhood: half-spread 15 bp + slippage 5 bp (Robinhood crypto execution embeds a spread markup)
Prices are rounded against us to the tick. Robinhood fractional orders require >= $1 notional.
"""
import math
from dataclasses import dataclass, replace

INDEX_ETFS = {'SPY', 'QQQ', 'IWM', 'DIA'}


@dataclass(frozen=True)
class CostModel:
    half_spread_bps: float
    slippage_bps: float
    fee_bps: float = 0.0
    tick: float = 0.01
    min_notional: float = 1.0

    def buy_fill(self, px: float) -> float:
        raw = px * (1 + (self.half_spread_bps + self.slippage_bps) / 1e4)
        return math.ceil(raw / self.tick - 1e-9) * self.tick

    def sell_fill(self, px: float) -> float:
        raw = px * (1 - (self.half_spread_bps + self.slippage_bps) / 1e4)
        return math.floor(raw / self.tick + 1e-9) * self.tick

    def net_return(self, entry_px: float, exit_px: float) -> float:
        buy, sell = self.buy_fill(entry_px), self.sell_fill(exit_px)
        return (sell * (1 - self.fee_bps / 1e4)) / (buy * (1 + self.fee_bps / 1e4)) - 1

    def round_trip_bps(self) -> float:
        return 2 * (self.half_spread_bps + self.slippage_bps + self.fee_bps)

    def scaled(self, k: float) -> 'CostModel':
        return replace(self, half_spread_bps=self.half_spread_bps * k, slippage_bps=self.slippage_bps * k, fee_bps=self.fee_bps * k)


ZERO = CostModel(0.0, 0.0, tick=1e-9)


def for_symbol(symbol: str) -> CostModel:
    if symbol.endswith('-USD') or symbol in ('BTC', 'ETH', 'DOGE'):
        return CostModel(15.0, 5.0)
    if symbol in INDEX_ETFS:
        return CostModel(0.5, 2.0)
    return CostModel(1.0, 3.0)
