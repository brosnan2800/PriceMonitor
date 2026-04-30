#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram 渠道适配器（次选平台）

功能：
  1. 推送：文本消息 + Inline Keyboard（对应飞书 MessageCard）
  2. 接收：python-telegram-bot polling 接收用户指令和按钮回调
"""

import json
import logging
import threading
from typing import Callable, Optional

from .base import BaseAdapter, IncomingMessage, OutgoingCard

logger = logging.getLogger(__name__)


class TelegramAdapter(BaseAdapter):
    """Telegram 渠道适配器"""

    platform_name = "telegram"

    def __init__(self, bot_token: str):
        self.bot_token = bot_token
        self._app = None
        self._on_message: Optional[Callable[[IncomingMessage], None]] = None
        self._thread: Optional[threading.Thread] = None

    # ── 发送消息 ──────────────────────────────────────────────────────

    def send_text(self, user_id: str, text: str) -> bool:
        if not self._app:
            return self._send_via_requests(user_id, text)
        import asyncio
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(
                self._app.bot.send_message(
                    chat_id=user_id,
                    text=text,
                    parse_mode="Markdown",
                    disable_web_page_preview=True
                )
            )
            loop.close()
            return True
        except Exception as e:
            logger.error(f"Telegram 发送文本失败: {e}")
            return False

    def _send_via_requests(self, user_id: str, text: str) -> bool:
        """无 Application 实例时的降级发送"""
        import requests
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={"chat_id": user_id, "text": text,
                      "parse_mode": "Markdown", "disable_web_page_preview": True},
                timeout=10
            )
            return resp.json().get("ok", False)
        except Exception as e:
            logger.error(f"Telegram requests 发送失败: {e}")
            return False

    def send_card(self, user_id: str, card: OutgoingCard) -> bool:
        """将 OutgoingCard 渲染为 Telegram Markdown + InlineKeyboard"""
        text = f"*{card.title}*\n\n{card.content}"
        if card.footer:
            text += f"\n\n_{card.footer}_"

        if not card.buttons:
            return self.send_text(user_id, text)

        # 构建 InlineKeyboardMarkup
        keyboard = []
        row = []
        for i, btn in enumerate(card.buttons):
            row.append({
                "text": btn.label,
                "callback_data": json.dumps({"action": btn.action, **btn.data},
                                            ensure_ascii=False)[:64]  # TG 限制64字节
            })
            if len(row) == 2 or i == len(card.buttons) - 1:
                keyboard.append(row)
                row = []

        import requests
        try:
            resp = requests.post(
                f"https://api.telegram.org/bot{self.bot_token}/sendMessage",
                json={
                    "chat_id": user_id,
                    "text": text,
                    "parse_mode": "Markdown",
                    "disable_web_page_preview": True,
                    "reply_markup": {"inline_keyboard": keyboard}
                },
                timeout=10
            )
            return resp.json().get("ok", False)
        except Exception as e:
            logger.error(f"Telegram 发送卡片失败: {e}")
            return False

    # ── Polling 监听 ──────────────────────────────────────────────────

    def start(self, on_message: Callable[[IncomingMessage], None]) -> None:
        self._on_message = on_message
        self._thread = threading.Thread(
            target=self._run_polling, daemon=True, name="telegram-polling"
        )
        self._thread.start()
        logger.info("Telegram polling 启动")

    def stop(self) -> None:
        if self._app:
            import asyncio
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._app.stop())
            loop.close()
        logger.info("Telegram 适配器停止")

    def _run_polling(self) -> None:
        try:
            from telegram.ext import Application, MessageHandler, CallbackQueryHandler, filters
            from telegram import Update
        except ImportError:
            logger.error("缺少 python-telegram-bot，请运行: pip install python-telegram-bot")
            return

        import asyncio

        async def _text_handler(update, context):
            if not update.message or not self._on_message:
                return
            inc = IncomingMessage(
                platform="telegram",
                user_id=str(update.effective_chat.id),
                username=update.effective_user.username or "",
                text=update.message.text or "",
                message_id=str(update.message.message_id),
                raw=update.to_dict()
            )
            self._on_message(inc)

        async def _callback_handler(update, context):
            if not update.callback_query or not self._on_message:
                return
            query = update.callback_query
            await query.answer()
            inc = IncomingMessage(
                platform="telegram",
                user_id=str(update.effective_chat.id),
                username=update.effective_user.username or "",
                text="",
                message_id=str(query.message.message_id),
                raw=update.to_dict(),
                callback_data=query.data
            )
            self._on_message(inc)

        async def _run():
            self._app = Application.builder().token(self.bot_token).build()
            self._app.add_handler(MessageHandler(filters.TEXT, _text_handler))
            self._app.add_handler(CallbackQueryHandler(_callback_handler))
            await self._app.initialize()
            await self._app.start()
            await self._app.updater.start_polling(drop_pending_updates=True)
            # 持续运行直到停止信号
            await self._app.updater.idle()

        asyncio.run(_run())
