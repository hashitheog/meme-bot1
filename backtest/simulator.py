import pandas as pd
import numpy as np
import random
from datetime import timedelta
from backtest.models import Signal

class MarketSimulator:
    def __init__(self, start_date, days=100):
        self.start_date = pd.to_datetime(start_date)
        self.end_date = self.start_date + timedelta(days=days)
        self.signals = []
        self.price_data = {} # {token_address: DataFrame}

    def generate_data(self, num_signals=50):
        print(f"Generating {num_signals} mock signals and price paths...")
        
        # 1. Generate Signals scattered over 100 days
        timestamps = pd.date_range(self.start_date, self.end_date, periods=num_signals*2)
        selected_times = random.sample(list(timestamps), num_signals)
        selected_times.sort()
        
        for i, ts in enumerate(selected_times):
            token_addr = f"0xToken{i}"
            score = random.choice([75, 82, 88, 92, 95]) # Mix of scores
            initial_price = random.uniform(0.0001, 0.01)
            
            sig = Signal(
                token_address=token_addr,
                symbol=f"MEME{i}",
                chain="solana",
                signal_time=ts,
                signal_score=score,
                price_at_signal=initial_price
            )
            self.signals.append(sig)
            
            # 2. Generate 1-minute Price Data for this token (24 hours)
            # Simulate a "pump and dump" or "moon" or "rug"
            self.price_data[token_addr] = self._generate_price_path(ts, initial_price)
            
        return self.signals, self.price_data

    def _generate_price_path(self, start_time, start_price):
        # Generate 1440 minutes (24h)
        # Volatility model
        minutes = 1440
        time_index = pd.date_range(start_time, periods=minutes, freq="1min")
        
        # Randomly choose a profile
        profile = random.choice(["moon", "dump", "chop", "volatile_up"])
        
        returns = np.random.normal(0, 0.02, minutes) # Base noise
        
        if profile == "moon":
            # Up drift
            drift = np.linspace(0, 0.002, minutes)
        elif profile == "dump":
            # Down drift
            drift = np.linspace(0, -0.003, minutes)
        elif profile == "volatile_up":
             drift = np.random.normal(0.0005, 0.01, minutes)
        else:
            drift = 0
            
        # Add big candles (shocks)
        if random.random() < 0.1: # Rug pull event
            rug_idx = random.randint(10, 200)
            returns[rug_idx] = -0.90 # -90% drop
            
        price_series = [start_price]
        for r, d in zip(returns, np.repeat(drift, 1) if isinstance(drift, int) else drift):
            change = r + d
            new_price = price_series[-1] * (1 + change)
            price_series.append(max(new_price, 0.00000001))
            
        df = pd.DataFrame({"price": price_series[1:]}, index=time_index)
        return df
