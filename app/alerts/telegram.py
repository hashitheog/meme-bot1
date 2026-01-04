import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from app.config import settings
from app.utils.logging_config import logger
from app.paper_trader import safe_trader, degen_trader

class TelegramBotService:
    def __init__(self):
        self.application = None
        self.chat_id = settings.TELEGRAM_CHAT_ID
        if settings.TELEGRAM_BOT_TOKEN:
            self.application = ApplicationBuilder().token(settings.TELEGRAM_BOT_TOKEN).build()
            self._register_handlers()
        else:
            logger.warning("Telegram Bot Token not missing. Bot will not run.")

    def _register_handlers(self):
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("balance", self.cmd_balance_all))
        self.application.add_handler(CommandHandler("balance1", self.cmd_balance_safe))
        self.application.add_handler(CommandHandler("balance2", self.cmd_balance_degen))
        
        self.application.add_handler(CommandHandler("active", self.cmd_active_all))
        self.application.add_handler(CommandHandler("active1", self.cmd_active_safe))
        self.application.add_handler(CommandHandler("active2", self.cmd_active_degen))
        
        self.application.add_handler(CommandHandler("stats", self.cmd_stats))

    async def start(self):
        if not self.application: return
        
        await self.application.initialize()
        await self.application.start()
        await self.application.updater.start_polling()
        logger.info("Telegram Bot Polling Started")

    async def stop(self):
        if not self.application: return
        await self.application.updater.stop()
        await self.application.stop()
        await self.application.shutdown()
        logger.info("Telegram Bot Stopped")

    # --- Command Handlers ---
    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text(
            "🟢 Meme Coin Analyst & Dual Paper Trader Active\n"
            "🛡️ *Safe*: /balance1, /active1\n"
            "⚔️ *Degen*: /balance2, /active2\n"
            "📊 *All*: /balance, /active",
            parse_mode="Markdown"
        )

    async def cmd_balance_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        s1 = safe_trader.get_stats()
        s2 = degen_trader.get_stats()
        msg = f"""💰 *Dual Strategy Overview*
🛡️ *Safe Shield*: {s1['balance']} ({s1['roi']})
⚔️ *Degen Sword*: {s2['balance']} ({s2['roi']})"""
        await update.message.reply_text(msg, parse_mode="Markdown")

    async def cmd_balance_safe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        s1 = safe_trader.get_stats()
        await update.message.reply_text(f"🛡️ *Safe Balance*: {s1['balance']} ({s1['roi']})", parse_mode="Markdown")

    async def cmd_balance_degen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        s2 = degen_trader.get_stats()
        await update.message.reply_text(f"⚔️ *Degen Balance*: {s2['balance']} ({s2['roi']})", parse_mode="Markdown")

    async def cmd_active_all(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._list_active(update, safe_trader, "🛡️ Safe Trades")
        await self._list_active(update, degen_trader, "⚔️ Degen Trades")

    async def cmd_active_safe(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._list_active(update, safe_trader, "🛡️ Safe Trades")

    async def cmd_active_degen(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await self._list_active(update, degen_trader, "⚔️ Degen Trades")

    async def _list_active(self, update, trader, title):
        trades = trader.active_trades
        if not trades:
            await update.message.reply_text(f"📂 *{title}*: None", parse_mode="Markdown")
            return
            
        lines = [f"📂 *{title}*"]
        for t in trades:
            lines.append(f"• {t.symbol} (MC: ${t.entry_mc:,.0f})")
        await update.message.reply_text("\n".join(lines), parse_mode="Markdown")

    async def cmd_stats(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        s1 = safe_trader.get_stats()
        s2 = degen_trader.get_stats()
        msg = f"""📊 *Stats (Wins/Losses)*
🛡️ Safe: {s1['wins']}W - {s1['losses']}L ({s1['win_rate']})
⚔️ Degen: {s2['wins']}W - {s2['losses']}L ({s2['win_rate']})"""
        await update.message.reply_text(msg, parse_mode="Markdown")

    # --- Alerting Interface ---
    async def send_alert(self, token_data: dict, score: float, analysis_result: dict, paper_trade=None, strategy_name="Unknown"):
        if not self.application: return

        # Escape special chars function
        def escape_md(text):
            special = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
            for char in special:
                text = text.replace(char, f"\\{char}")
            return text

        # Re-build message without raw f-strings for untrusted input
        name = token_data.get("baseToken", {}).get("name", "Unknown")
        symbol = token_data.get("baseToken", {}).get("symbol", "UNK")
        chain = token_data.get("chainId", "unknown")
        liquidity = token_data.get("liquidity", {}).get("usd", 0)
        ai_summary = analysis_result.get("summary", "No summary.")
        verdict = analysis_result.get("verdict", "CAUTION")

        safe_name = escape_md(name)
        safe_symbol = escape_md(symbol)
        safe_chain = escape_md(chain.upper())
        safe_verdict = escape_md(verdict)
        safe_summary = escape_md(ai_summary)

        safe_liquidity = escape_md(f"${liquidity:,.0f}")
        safe_score = escape_md(f"{score:.1f}")
        safe_strategy = escape_md(strategy_name)

        header = "🚀 *GEM DETECTED*" if "Shield" in strategy_name else "🎰 *DEGEN PLAY DETECTED*"
        
        message = f"""
{header}
*Strategy:* {safe_strategy}

*Name:* {safe_name} \({safe_symbol}\)
*Chain:* {safe_chain}
*Liquidity:* {safe_liquidity}
*Final Score:* {safe_score}/100

🧠 *AI Verdict:* {safe_verdict}
_{safe_summary}_
"""
        # Append Paper Trade Info
        if paper_trade:
             message += f"""
🧪 *PAPER TRADE OPENED*
Risk: {escape_md(str(paper_trade.risk_pct))}%
Position: ${escape_md(f"{paper_trade.position_size_usd:.2f}")}
Entry MC: ${escape_md(f"{paper_trade.entry_mc:,.0f}")}
"""

        try:
            await self.application.bot.send_message(
                chat_id=self.chat_id,
                text=message,
                parse_mode="MarkdownV2", # Use V2 for safer escaping
                disable_web_page_preview=True
            )
        except Exception as e:
            logger.error("Failed to send Telegram alert", error=str(e))
            
    async def send_startup_message(self):
        # ... existing ...
        if not self.application: return
        try:
             await self.application.bot.send_message(
                chat_id=self.chat_id,
                text="🟢 *Dual Strategy Bot Started*\nReady for Safe & Degen plays.",
                parse_mode="Markdown"
            )
        except: pass

    async def send_trade_update(self, update_type: str, trade, extra=None):
        # ... existing ...
        pass # Not changing logic here for now, kept brief.

        if not self.application: return
        
        if update_type == "TP":
            msg = f"📈 *PAPER TP HIT*\nToken: ${trade.symbol}\nSold: {extra*100:.0f}%\nRealized PnL: ${trade.realized_pnl:.2f}"
            
        elif update_type == "CLOSE":
            emoji = "✅" if trade.realized_pnl > 0 else "❌"
            msg = f"{emoji} *PAPER TRADE CLOSED*\nToken: ${trade.symbol}\nReason: {trade.exit_reason}\nFinal PnL: ${trade.realized_pnl:.2f}"
            
        else:
            return

        try:
            await self.application.bot.send_message(chat_id=self.chat_id, text=msg, parse_mode="Markdown")
        except Exception:
            pass

telegram_service = TelegramBotService()

