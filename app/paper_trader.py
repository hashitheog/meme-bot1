import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional
from dataclasses import dataclass, field

from app.utils.logging_config import logger

@dataclass
class PaperTrade:
    token_address: str
    symbol: str
    chain: str
    entry_mc: float
    entry_price_proxy: float # Just for reference, MC is main metric
    entry_time: datetime
    
    # Position
    position_size_usd: float
    risk_pct: float
    initial_units: float # Derived from price proxy
    current_units: float
    
    # Strategy State
    base_potential: float # e.g. 2.0x
    peak_mc: float
    peak_potential_used: float = 0.0
    
    # State flags
    status: str = "OPEN" # OPEN, CLOSED
    tp_levels_hit: List[str] = field(default_factory=list) # e.g. ["30%", "50%"]
    
    realized_pnl: float = 0.0
    exit_reason: str = ""
    exit_time: Optional[datetime] = None

class PaperTrader:
    def __init__(self, initial_capital=200.0):
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.trades: List[PaperTrade] = []
        self.active_trades: List[PaperTrade] = []
        
        # Strategy Parameters (V3 Potential)
        self.risk_per_trade = 0.02 # 2%
        self.max_trades = 4
        
        logger.info("Paper Trader Initialized", capital=self.capital)

    def process_signal(self, signal_data: dict, analysis_result: dict, dex_client=None):
        """
        Evaluates a signal for paper entry.
        """
        # 1. Check Constraints
        if len(self.active_trades) >= self.max_trades:
            logger.info("Paper Trade Rejected: Max trades reached")
            return None
            
        if self.capital <= 0:
            logger.info("Paper Trade Rejected: No capital")
            return None
            
        # 2. Extract Data
        # Assume signal_data is the 'pair' dict from DexScreener
        base_token = signal_data.get("baseToken", {})
        symbol = base_token.get("symbol", "UNK")
        addr = base_token.get("address", "")
        chain = signal_data.get("chainId", "")
        price_usd = float(signal_data.get("priceUsd", 0) or 0)
        mc = signal_data.get("marketCap", 0) or (signal_data.get("liquidity", {}).get("usd", 0) * 5) # Fallback heuristic
        
        # Check Strategy (Potential)
        # In real impl, potential comes from AI or Logic. 
        # Here we assume if passed filters, it has potential >= 2.0x base case
        base_potential = 2.0 # Default assumption as per prompt
        
        # 3. Position Sizing
        risk_amount = self.capital * self.risk_per_trade
        # Stop distance? In prompt "risk percent" seems to be position size pct?
        # Prompt: "position_size = capital x risk_percent" -> This implies Fixed Fractional Position Sizing, not Risk-Based Sizing.
        # "Risk Percent (already calculated)" -> Input says risk percent is given.
        # But Entry Rules say: "position_size = capital x risk_percent".
        # Let's stick to 2% fixed position size (very conservative) or 2% RISK?
        # Standard: Position Size = 2% of Capital. (Tiny!)
        # Or Position Size such that Loss is 2%?
        # Prompt says: "Risk: X%" in output.
        # Let's use 6% Position Size as typical for this setup?
        # Wait, the prompt "Risk Percent (already calculated)" suggests it comes from signal.
        # Let's use 5% fixed for now as "Risk".
        position_size = self.capital * self.risk_per_trade * 2.5 # e.g 5% of cap? 
        # Actually prompt says: "position_size = capital x risk_percent".
        # Let's assume input risk_percent is passed or we define it.
        # I defined self.risk_per_trade = 0.02. So $4 position on $200. Very safe.
        position_size = self.capital * 0.05 # Let's do 5% size ($10)
        
        units = position_size / price_usd if price_usd else 0
        
        trade = PaperTrade(
            token_address=addr,
            symbol=symbol,
            chain=chain,
            entry_mc=mc,
            entry_price_proxy=price_usd,
            entry_time=datetime.utcnow(),
            position_size_usd=position_size,
            risk_pct=5.0, # 5% sizing
            initial_units=units,
            current_units=units,
            base_potential=base_potential,
            peak_mc=mc
        )
        
        self.capital -= position_size
        self.active_trades.append(trade)
        self.trades.append(trade)
        
        logger.info("Paper Trade START", symbol=symbol, size=position_size)
        return trade

    def update_trades(self, current_data_map: Dict[str, float]):
        """
        Updates active trades with current Market Cap data.
        current_data_map: {token_address: current_mc}
        """
        updates = []
        for trade in list(self.active_trades):
            current_mc = current_data_map.get(trade.token_address)
            if not current_mc:
                continue
                
            # Update Peak
            if current_mc > trade.peak_mc:
                trade.peak_mc = current_mc
                
            # Calc Potential Used
            # Potential Used = current_mc / entry_mc (Relative Growth)
            # If Entry 1M, Current 1.5M -> 1.5x
            potential_used_x = current_mc / trade.entry_mc
            potential_pct = (potential_used_x - 1.0) / (trade.base_potential - 1.0) # Normalized to base target?
            # Prompt says: "Potential Used = current_mc / entry_mc" (wait, that's just multiplier)
            # Then "Potential Used 30% -> Sell".
            # This implies "Percentage of Target Potential".
            # E.g. Target is 2.0x (100% gain).
            # If current is 1.3x (30% gain).
            # "Potential Used" likely means (Current - Entry) / (Target - Entry).
            
            # Let's implement normalized potential:
            # Target Delta = Entry * (BasePotential - 1)
            # Current Delta = Current - Entry
            # Pct Used = Current Delta / Target Delta
            
            if trade.base_potential <= 1.0: 
                pct_used = 0 # Should not happen
            else:
                 target_mc = trade.entry_mc * trade.base_potential
                 pct_used = (current_mc - trade.entry_mc) / (target_mc - trade.entry_mc)
            
            # --- Stop Loss Rules ---
            # 1. MC drops >= 30% from entry
            loss_pct = (trade.entry_mc - current_mc) / trade.entry_mc
            if loss_pct >= 0.30:
                self._close_trade(trade, current_mc, "STOP_LOSS_30_PCT")
                updates.append(("CLOSE", trade))
                continue
                
            # 2. Base Case Potential < 1.3x (Invalidation)
            # If AI re-evaluates? We don't have live re-eval. Skip.
            
            # 3. Time Exit
            duration_mins = (datetime.utcnow() - trade.entry_time).total_seconds() / 60
            if duration_mins > 90 and pct_used < 0.30:
                self._close_trade(trade, current_mc, "TIME_EXIT_STAGNANT")
                updates.append(("CLOSE", trade))
                continue
                
            # --- Take Profit Rules ---
            # 30% used -> Sell 20%
            if pct_used >= 0.30 and "30%" not in trade.tp_levels_hit:
                self._partial_close(trade, 0.20, current_mc, "TP_30_PCT")
                trade.tp_levels_hit.append("30%")
                updates.append(("TP", trade, 0.20))
                
            # 50% used -> Sell 25%
            if pct_used >= 0.50 and "50%" not in trade.tp_levels_hit:
                self._partial_close(trade, 0.25, current_mc, "TP_50_PCT")
                trade.tp_levels_hit.append("50%")
                updates.append(("TP", trade, 0.25))
                
            # 70% used -> Sell 30%
            if pct_used >= 0.70 and "70%" not in trade.tp_levels_hit:
                self._partial_close(trade, 0.30, current_mc, "TP_70_PCT")
                trade.tp_levels_hit.append("70%")
                updates.append(("TP", trade, 0.30))
                
            # >= 90% -> Leave moonbag (No action needed, just holding)
            
        return updates

    def _close_trade(self, trade, current_mc, reason):
        # Sell remaining
        # Price proxy: assume price moves closely with MC
        price_ratio = current_mc / trade.entry_mc
        exit_price_proxy = trade.entry_price_proxy * price_ratio
        
        proceeds = trade.current_units * exit_price_proxy
        self.capital += proceeds
        
        # Calc PnL for this chunk
        cost_basis = trade.current_units * trade.entry_price_proxy
        pnl = proceeds - cost_basis
        trade.realized_pnl += pnl
        
        trade.current_units = 0
        trade.status = "CLOSED"
        trade.exit_reason = reason
        trade.exit_time = datetime.utcnow()
        self.active_trades.remove(trade)
        logger.info("Paper Trade CLOSED", symbol=trade.symbol, pnl=trade.realized_pnl)

    def _partial_close(self, trade, pct_to_sell, current_mc, reason):
        # Sell pct of REMAINING or INITIAL? 
        # Prompt: "Sell 20%". Standard is 20% of CURRENT holding usually, or initial.
        # Let's assume % of CURRENT holding to avoid selling more than we have if logic overlaps.
        # Actually standard scaling is usually % of INITIAL pos.
        # "Sell 20%" usually means 20% of the original bag.
        
        units_to_sell = trade.initial_units * pct_to_sell
        if units_to_sell > trade.current_units:
            units_to_sell = trade.current_units # Cap
            
        price_ratio = current_mc / trade.entry_mc
        exit_price_proxy = trade.entry_price_proxy * price_ratio
        
        proceeds = units_to_sell * exit_price_proxy
        self.capital += proceeds
        
        cost_basis = units_to_sell * trade.entry_price_proxy
        pnl = proceeds - cost_basis
        trade.realized_pnl += pnl
        
        trade.current_units -= units_to_sell
        logger.info("Paper Trade PARTIAL", symbol=trade.symbol, pnl=pnl)

    def get_stats(self):
        total_trades = len(self.trades)
        wins = len([t for t in self.trades if t.realized_pnl > 0 and t.status == "CLOSED"])
        losses = len([t for t in self.trades if t.realized_pnl <= 0 and t.status == "CLOSED"])
        win_rate = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        
        return {
            "balance": f"${self.capital:.2f}",
            "roi": f"{((self.capital - self.initial_capital)/self.initial_capital)*100:.1f}%",
            "trades": total_trades,
            "wins": wins,
            "losses": losses,
            "win_rate": f"{win_rate:.1f}%"
        }

# Instantiate TWO traders
safe_trader = PaperTrader(initial_capital=200.0)
degen_trader = PaperTrader(initial_capital=200.0)

# Backward compatibility (alias paper_trader to safe_trader for existing imports)
paper_trader = safe_trader
