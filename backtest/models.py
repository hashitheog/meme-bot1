from dataclasses import dataclass, field
from typing import List, Dict, Optional
from datetime import datetime
import pandas as pd

@dataclass
class Signal:
    token_address: str
    symbol: str
    chain: str
    signal_time: pd.Timestamp
    signal_score: float
    price_at_signal: float

@dataclass
class Trade:
    token_address: str
    entry_price: float
    entry_time: pd.Timestamp
    position_size_usd: float # Initial size
    entry_score: float
    
    current_units: float # Units held
    realized_pnl: float = 0.0
    status: str = "OPEN" # OPEN, CLOSED
    
    # Levels
    ath_price: float = 0.0
    stop_loss_price: float = 0.0
    
    # State flags
    tp1_hit: bool = False
    tp2_hit: bool = False
    tp3_hit: bool = False
    
    exit_reason: str = ""
    exit_time: Optional[pd.Timestamp] = None
    
    def current_value(self, current_price: float) -> float:
        return self.current_units * current_price

@dataclass
class BacktestResult:
    trades: List[Trade]
    equity_curve: List[Dict] # {time, equity}
    final_capital: float
    metrics: Dict
