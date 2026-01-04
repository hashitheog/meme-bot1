import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest.simulator import MarketSimulator
from backtest.engine import BacktestEngine
import pandas as pd
import matplotlib.pyplot as plt

def main():
    print("--- 🚀 Meme Coin Strategy V2 Backtest ---")
    
    # 1. Generate Data
    sim = MarketSimulator(start_date="2024-01-01", days=100)
    signals, price_data = sim.generate_data(num_signals=100)
    
    # 2. Run Engine
    engine = BacktestEngine(initial_capital=200.0)
    result = engine.run(signals, price_data)
    
    # 3. Analysis & Output
    if not result:
        print("Backtest failed or no result.")
        return

    total_trades = len(result.trades)
    winning_trades = [t for t in result.trades if t.realized_pnl > 0]
    win_rate = (len(winning_trades) / total_trades * 100) if total_trades > 0 else 0
    
    net_pnl = result.final_capital - engine.initial_capital
    roi = (net_pnl / engine.initial_capital) * 100
    
    # Max Drawdown
    equity_series = pd.DataFrame(result.equity_curve)
    if not equity_series.empty:
        equity_series.set_index('time', inplace=True)
        equity_series['peak'] = equity_series['equity'].cummax()
        equity_series['drawdown'] = (equity_series['equity'] - equity_series['peak']) / equity_series['peak']
        max_dd = equity_series['drawdown'].min() * 100
    else:
        max_dd = 0.0

    print("\n" + "="*40)
    print("📊 BACKTEST RESULTS CHECK")
    print("="*40)
    print(f"Signals Tested:   {len(signals)}")
    print(f"Trades Taken:     {total_trades}")
    print(f"Win Rate:         {win_rate:.2f}%")
    print("-" * 20)
    print(f"Initial Capital:  ${engine.initial_capital:.2f}")
    print(f"Final Capital:    ${result.final_capital:.2f}")
    print(f"Net PnL:          ${net_pnl:.2f}")
    print(f"Net ROI:          {roi:.2f}%")
    print(f"Max Drawdown:     {max_dd:.2f}%")
    print("="*40)
    
    # Verification of Logic
    print("\n🔍 Trade Logic Verification (First 5 Trades):")
    for t in result.trades[:5]:
        print(f"Token: {t.token_address} | Entry: ${t.entry_price:.4f} | Exit: {t.exit_reason} | PnL: ${t.realized_pnl:.2f}")

    # Plot
    if not equity_series.empty:
        plt.figure(figsize=(10, 6))
        plt.plot(equity_series.index, equity_series['equity'], label='Equity')
        plt.title('Backtest Equity Curve')
        plt.xlabel('Date')
        plt.ylabel('Capital ($)')
        plt.legend()
        plt.grid(True)
        plt.savefig('backtest_equity.png')
        print("\n📈 Equity curve saved to 'backtest_equity.png'")

if __name__ == "__main__":
    main()
