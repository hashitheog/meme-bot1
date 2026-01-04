# AI Meme Coin Analysis Platform

A high-performance, async Python application that monitors DexScreener for newly listed meme coins, scores them using AI and on-chain metrics, and alerts via Telegram.

## 🚀 Features
- **Real-time Monitoring**: Polling DexScreener periodically.
- **Fast Filtering**: In-memory checks for liquidity, age, and volume to reject garbage instantly.
- **AI Analysis**: Uses OpenAI/LLM to detect scams, analyze sentiment, and rate "meme potential".
- **On-Chain Checks**: Stubs for verifying HoneyPots, LP locking, and Dev composition.
- **Telegram Alerts**: High-quality formatted alerts for tokens passing all checks.
- **Infrastructure**: Asyncio, Redis Caching, SQLite/PostgreSQL, Structured Logging.

## 🛠 Prerequisites
- Python 3.11+
- Redis (Running locally or remote)
- OpenAI API Key

## 📦 Setup

1. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

2. **Environment Configuration**
   Copy `.env.example` to `.env` and fill in your keys:
   ```bash
   cp .env.example .env
   ```
   *Required Variables:*
   - `OPENAI_API_KEY`: For AI scoring.
   - `TELEGRAM_BOT_TOKEN` & `TELEGRAM_CHAT_ID`: For alerts.
   - `DEXSCREENER_API_URL`: Default provided.

3. **Run Redis**
   Make sure Redis is running on port 6379 or update `REDIS_URL` in `.env`.

4. **Run the Bot**
   ```bash
   python -m app.main
   ```

## 🛠 Utility Scripts (in `scripts/`)
- **System Verification**: Checks API keys & health.
  ```bash
  python scripts/verify_setup.py
  ```
- **Telegram Simulation**: Tests alerts & dual strategy routing.
  ```bash
  python scripts/test_telegram_flow.py
  ```
- **Scraper Test**: Verifies DexScreener connection.
  ```bash
  python scripts/test_scraper.py
  ```

## 🧠 System Architecture
- **Dual Strategy Engine**:
  - 🛡️ **Safe Shield**: Strict rules (No Mintable), $200 Balance.
  - ⚔️ **Degen Sword**: Risky (Mintable OK if High AI Score), $200 Balance.
- **Scanner**: Polls DexScreener via Playwright (Stealth Mode).
- **AI Engine**: DeepSeek/Gemini/OpenAI risk analysis.

