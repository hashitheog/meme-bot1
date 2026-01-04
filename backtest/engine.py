import pandas as pd
from typing import List, Dict
from backtest.models import Signal, Trade, BacktestResult

class BacktestEngine:
    def __init__(self, initial_capital=200.0):
        self.capital = initial_capital
        self.initial_capital = initial_capital
        self.equity = initial_capital
        self.trades: List[Trade] = []
        self.active_trades: List[Trade] = []
        
        self.daily_start_equity = initial_capital
        self.current_day = None
        self.daily_loss_limit_hit = False
        
        self.equity_curve = []

    def run(self, signals: List[Signal], price_data: Dict[str, pd.DataFrame]):
        """
        Main Event Loop
        """
        # Sort signals by time
        signals.sort(key=lambda x: x.signal_time)
        
        all_times = []
        for df in price_data.values():
            all_times.extend(df.index.tolist())
        
        if not all_times:
            print("No price data found.")
            return

        min_time = min(all_times)
        max_time = max(all_times)
        
        print(f"Running backtest from {min_time} to {max_time}...")
        print(f"Loaded {len(signals)} signals.")
        
        current_time = min_time
        signal_idx = 0
        
        while current_time <= max_time:
            # 1. Day Reset Logic
            is_new_day = self.current_day != current_time.date()
            if is_new_day:
                self.current_day = current_time.date()
                self.daily_start_equity = self.equity
                self.daily_loss_limit_hit = False
            
            # 2. Update Active Trades (Price Check)
            current_unrealized_value = 0.0
            self._update_trades(current_time, price_data)
            
            # Calculate Equity
            for t in self.active_trades:
                df = price_data.get(t.token_address)
                if df is not None and current_time in df.index:
                    current_unrealized_value += t.current_units * df.loc[current_time]['price']
            
            self.equity = self.capital + current_unrealized_value
            
            # 3. Process New Signals (if any at this minute)
            while signal_idx < len(signals) and signals[signal_idx].signal_time <= current_time:
                sig = signals[signal_idx]
                self._process_signal(sig)
                signal_idx += 1
            
            # 4. Record Equity
            self.equity_curve.append({
                "time": current_time,
                "equity": self.equity,
                "capital": self.capital
            })
            
            # Time Step
            current_time += pd.Timedelta(minutes=1)
            
            # Optimization: If no active trades and next signal is far, jump
            if not self.active_trades and signal_idx < len(signals):
                next_sig_time = signals[signal_idx].signal_time
                if next_sig_time > current_time:
                    jump_to = next_sig_time - pd.Timedelta(minutes=1)
                    if jump_to > current_time:
                        current_time = jump_to

        return self._generate_results()

    def _process_signal(self, sig: Signal):
        print(f"DEBUG: Processing Signal {sig.symbol} Score={sig.signal_score} Time={sig.signal_time}")
        # Filter: Score < 80
        if sig.signal_score < 80:
            print("  -> Rejected: Score < 80")
            return

        # Filter: Max Concurrent Trades
        if len(self.active_trades) >= 4:
            print(f"  -> Rejected: Max Trades ({len(self.active_trades)})")
            return

        # Filter: Daily Loss Limit
        if self.daily_loss_limit_hit:
            print("  -> Rejected: Daily Loss Limited")
            return
            
        # Position Sizing (V3 Conservative)
        risk_pct = 0.0
        if sig.signal_score >= 90: risk_pct = 0.025 # Was 6%
        elif sig.signal_score >= 85: risk_pct = 0.020 # Was 5%
        else: risk_pct = 0.015 # Was 4%
        
        risk_amount = self.capital * risk_pct
        initial_sl_pct = 0.15 # Phase 1 SL: Tighter (was 0.20)
        
        pos_size_usd = risk_amount / initial_sl_pct
        
        # Check if we have enough capital
        if pos_size_usd > self.capital:
             # Scale down to max capital if needed, but safer to skip to avoid over-exposure
             # But let's cap it at available capital
             pos_size_usd = self.capital
        
        # print(f"  -> Accepted. Size=${pos_size_usd:.2f} (Risk=${risk_amount:.2f})")
        
        # Execute Entry
        self.capital -= pos_size_usd
        units = pos_size_usd / sig.price_at_signal
        
        trade = Trade(
            token_address=sig.token_address,
            entry_price=sig.price_at_signal,
            entry_time=sig.signal_time,
            position_size_usd=pos_size_usd,
            entry_score=sig.signal_score,
            current_units=units,
            ath_price=sig.price_at_signal,
            stop_loss_price=sig.price_at_signal * (1 - initial_sl_pct)
        )
        self.active_trades.append(trade)
        self.trades.append(trade)

    def _update_trades(self, current_time, price_data):
        for trade in list(self.active_trades):
            # Get current price
            df = price_data.get(trade.token_address)
            if df is None: continue
            
            # Lookup price at this minute
            try:
                # We generated data with exact minute index
                current_price = df.loc[current_time]['price']
            except KeyError:
                # Price data ended or missing
                # FIX: If data ends, we must close the position or mark it as "End of Data"
                # Since we only generated 24h of data, we assume market closed or track ending.
                # Let's close it at last known price? OR just skip?
                # If we skip, it hangs forever.
                # We should close it if we are past the data range.
                if not df.empty and current_time > df.index[-1]:
                     last_price = df.iloc[-1]['price']
                     self._close_trade(trade, last_price, df.index[-1], "END_OF_DATA")
                continue
                
            # Update ATH
            if current_price > trade.ath_price:
                trade.ath_price = current_price
                
            # --- Stop Loss Logic ---
            # Phase 1: First 15 mins (-20%) -> Already set in init
            # Phase 2: > 15 mins (-30% hard)
            minutes_in = (current_time - trade.entry_time).total_seconds() / 60
            
            if minutes_in > 15:
                # Update Hard Stop if needed (only if loose, constrain to -30%)
                hard_stop = trade.entry_price * 0.70
                if trade.stop_loss_price > hard_stop: 
                     pass # Current SL is tighter (e.g. trailing), keep it
                else:
                     trade.stop_loss_price = hard_stop # Tighten to -30%
            
            # Trailing Stop: ATH >= +40% -> Stop = ATH - 35%
            roi_ath = (trade.ath_price - trade.entry_price) / trade.entry_price
            if roi_ath >= 0.40:
                trail_stop = trade.ath_price * (1 - 0.35)
                if trail_stop > trade.stop_loss_price:
                    trade.stop_loss_price = trail_stop
            
            # Check Stop Hit
            if current_price <= trade.stop_loss_price:
                self._close_trade(trade, current_price, current_time, "STOP_LOSS")
                continue
                
            # --- Take Profit Logic (V3) ---
            roi = (current_price - trade.entry_price) / trade.entry_price
            
            # TP1: +40% -> Sell 50% (Secure Break Even + Profit)
            if roi >= 0.40 and not trade.tp1_hit:
                self._partial_close(trade, 0.50, current_price, "TP1")
                trade.tp1_hit = True
                # Move Stop to Entry?
                trade.stop_loss_price = max(trade.stop_loss_price, trade.entry_price)
                
            # TP2: +100% -> Sell 25% of INITIAL (which is 50% of REMAINING approx)
            if roi >= 1.00 and not trade.tp2_hit:
                self._partial_close(trade, 0.25, current_price, "TP2")
                trade.tp2_hit = True

            # TP3: +200% -> Sell remaining moonbag or partial? 
            # Prompt V2 said "sell 25%", leaving 25%.
            # V3 Strategy: TP1=50%, TP2=25%, TP3=15%? Leaving 10%?
            # Let's do TP3 sell 15% (Leaving 10% moonbag)
            if roi >= 2.00 and not trade.tp3_hit:
                self._partial_close(trade, 0.15, current_price, "TP3")
                trade.tp3_hit = True
                
            # --- Time Based Exit ---
            # 90 mins, ROI between -10% and +20%
            if minutes_in >= 90:
                if -0.10 <= roi <= 0.20:
                     self._close_trade(trade, current_price, current_time, "TIME_EXIT")
                     continue

            # Check Daily Loss Limit
            day_pnl = self.equity - self.daily_start_equity
            if day_pnl < -(self.daily_start_equity * 0.10):
                self.daily_loss_limit_hit = True

    def _close_trade(self, trade, price, time, reason):
        # Sell all remaining units
        proceeds = trade.current_units * price
        self.capital += proceeds
        trade.realized_pnl += (proceeds - (trade.current_units * trade.entry_price)) # Approx pnl add
        trade.current_units = 0
        trade.status = "CLOSED"
        trade.exit_reason = reason
        trade.exit_time = time
        self.active_trades.remove(trade)
        # print(f"  DEBUG: Close Trade {trade.token_address} at {price:.4f} Reason={reason}")
        
    def _partial_close(self, trade, pct_of_initial, price, reason):
        # Sell pct of INITIAL units
        initial_units = trade.position_size_usd / trade.entry_price
        units_to_sell = initial_units * pct_of_initial
        
        if units_to_sell > trade.current_units:
            units_to_sell = trade.current_units # Cap at what we have
            
        proceeds = units_to_sell * price
        self.capital += proceeds
        trade.current_units -= units_to_sell
        
        # Track realized PnL
        # Cost basis of sold units
        cost = units_to_sell * trade.entry_price
        trade.realized_pnl += (proceeds - cost)
        # print(f"  DEBUG: Partial Close {trade.token_address} {pct_of_initial*100}% at {price:.4f} Reason={reason}")

    def _generate_results(self):
        return BacktestResult(
            trades=self.trades,
            equity_curve=self.equity_curve,
            final_capital=self.capital,
            metrics={}
        )

    @property
    def current_equity(self):
        return self.equity
