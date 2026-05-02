#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书渠道适配器（主平台）

接收模式：WebSocket 长连接（lark-oapi SDK）
  - 无需公网 IP / ngrok
  - 自动断线重连（auto_reconnect=True）
  - 完美适配极空间 Docker + 每日重启场景

推送模式：飞书开放平台 IM API
  - 文本消息
  - MessageCard 富交互卡片（按钮/表格）
"""

import json
import logging
import threading
import time
from typing import Callable, Dict, Optional

import requests

from .base import BaseAdapter, CardInput, IncomingMessage, OutgoingCard

logger = logging.getLogger(__name__)

_SEND_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
_AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"


class FeishuAdapter(BaseAdapter):
    """
    飞书渠道适配器
    接收：lark-oapi WebSocket 长连接（无需公网）
    推送：飞书 IM API（tenant_access_token）
    """

    platform_name = "feishu"

    def __init__(self, app_id: str, app_secret: str):
        self.app_id = app_id
        self.app_secret = app_secret

        self._token: Optional[str] = None
        self._token_expire: float = 0.0
        self._ws_client = None
        self._ws_thread: Optional[threading.Thread] = None
        self._on_message: Optional[Callable[[IncomingMessage], None]] = None
        # 消息去重：缓存最近 200 条 message_id，防止飞书重发导致重复处理
        self._seen_ids: list = []

    # ── Token 管理（推送用） ──────────────────────────────────────────

    def _refresh_token(self) -> bool:
        try:
            resp = requests.post(_AUTH_URL, json={
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }, timeout=10)
            data = resp.json()
            if data.get("code") == 0:
                self._token = data["tenant_access_token"]
                self._token_expire = time.time() + data.get("expire", 7200) - 300
                return True
            logger.error(f"飞书 token 获取失败: {data}")
        except Exception as e:
            logger.error(f"飞书 token 刷新异常: {e}")
        return False

    def _get_token(self) -> Optional[str]:
        if not self._token or time.time() >= self._token_expire:
            self._refresh_token()
        return self._token

    # ── 发送消息 ──────────────────────────────────────────────────────

    def _send(self, receive_id: str, receive_id_type: str,
              msg_type: str, content: Dict) -> bool:
        token = self._get_token()
        if not token:
            return False
        try:
            resp = requests.post(
                _SEND_URL,
                headers={"Authorization": f"Bearer {token}",
                         "Content-Type": "application/json; charset=utf-8"},
                params={"receive_id_type": receive_id_type},
                json={
                    "receive_id": receive_id,
                    "msg_type": msg_type,
                    "content": json.dumps(content, ensure_ascii=False)
                },
                timeout=10
            )
            result = resp.json()
            if result.get("code") == 0:
                return True
            logger.error(f"飞书发送失败: {result}")
        except Exception as e:
            logger.error(f"飞书发送异常: {e}")
        return False

    def send_text(self, user_id: str, text: str) -> bool:
        return self._send(user_id, "open_id", "text", {"text": text})

    def send_card(self, user_id: str, card: OutgoingCard) -> bool:
        card_json = _build_feishu_card(card)
        return self._send(user_id, "open_id", "interactive", card_json)

    # ── WebSocket 长连接（接收消息） ──────────────────────────────────

    def start(self, on_message: Callable[[IncomingMessage], None]) -> None:
        self._on_message = on_message
        self._ws_thread = threading.Thread(
            target=self._run_ws, daemon=True, name="feishu-ws"
        )
        self._ws_thread.start()
        logger.info("飞书 WebSocket 长连接启动（无需公网 IP）")

    def stop(self) -> None:
        logger.info("飞书适配器停止")

    def _run_ws(self) -> None:
        try:
            import lark_oapi as lark
            from lark_oapi.ws import Client as WsClient
        except ImportError:
            logger.error("缺少 lark-oapi，请运行: pip install lark-oapi")
            return

        # 构建事件处理器
        event_handler = (
            lark.EventDispatcherHandler.builder("", "")
            # 接收用户文本消息
            .register_p2_im_message_receive_v1(self._on_receive_message)
            # 接收卡片按钮回调
            .register_p2_card_action_trigger(self._on_card_action)
            .build()
        )

        # 构建 WebSocket 客户端，auto_reconnect=True 自动断线重连
        self._ws_client = WsClient(
            app_id=self.app_id,
            app_secret=self.app_secret,
            event_handler=event_handler,
            auto_reconnect=True,
        )

        # 阻塞运行（断线自动重连）
        self._ws_client.start()

    def _on_receive_message(self, event) -> None:
        """处理用户发来的文本消息"""
        if not self._on_message:
            return
        try:
            sender = event.event.sender
            msg = event.event.message
            user_id = sender.sender_id.open_id or ""
            mid = msg.message_id or ""

            # 去重：同一条消息飞书可能因超时重发
            if mid and mid in self._seen_ids:
                logger.debug(f"重复消息已忽略: {mid}")
                return
            if mid:
                self._seen_ids.append(mid)
                if len(self._seen_ids) > 200:
                    self._seen_ids.pop(0)

            if msg.message_type == "text":
                try:
                    text = json.loads(msg.content).get("text", "").strip()
                except Exception:
                    text = ""
            else:
                text = f"[{msg.message_type}]"

            inc = IncomingMessage(
                platform="feishu",
                user_id=user_id,
                username=getattr(sender.sender_id, "user_id", ""),
                text=text,
                message_id=mid,
                raw={}
            )
            self._on_message(inc)
        except Exception as e:
            logger.error(f"飞书消息解析异常: {e}", exc_info=True)

    def _on_card_action(self, event):
        """处理卡片按钮点击回调（P2 格式）"""
        from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse
        resp = P2CardActionTriggerResponse()

        if not self._on_message:
            return resp
        try:
            # lark-oapi P2 卡片回调: event.event.operator / event.event.action
            ev = event.event
            operator = ev.operator if ev else None
            action = ev.action if ev else None
            user_id = (operator.open_id or "") if operator else ""

            # 去重：飞书卡片回调也可能重发，用 event_id 去重
            event_id = getattr(event, "header", None)
            event_id = getattr(event_id, "event_id", None) if event_id else None
            if event_id:
                if event_id in self._seen_ids:
                    logger.debug(f"重复卡片回调已忽略: {event_id}")
                    return resp
                self._seen_ids.append(event_id)
                if len(self._seen_ids) > 200:
                    self._seen_ids.pop(0)

            btn_value = dict(action.value or {}) if action else {}
            tag = getattr(action, "tag", None) if action else None
            form_value = getattr(action, "form_value", None) if action else None

            if tag == "input":
                # 单输入框回调（Enter 触发）：name 格式 "{action}.{field}"
                name = getattr(action, "name", "") or ""
                input_value = getattr(action, "input_value", None) or ""
                if "." in name:
                    action_name, field_name = name.split(".", 1)
                else:
                    action_name, field_name = "do_quote", name or "symbol"
                merged = {"action": action_name, field_name: input_value}
            elif form_value:
                # 多输入框表单提交（form 容器内的按钮触发，form_value 含所有字段）
                merged = dict(btn_value)
                merged.update(dict(form_value))
            else:
                # 普通按钮回调
                merged = dict(btn_value)

            callback_data = json.dumps(merged, ensure_ascii=False)
            logger.info(f"[card_action] tag={tag} merged={callback_data}")

            inc = IncomingMessage(
                platform="feishu",
                user_id=user_id,
                username=(operator.user_id or "") if operator else "",
                text="",
                message_id="",
                raw={},
                callback_data=callback_data
            )
            self._on_message(inc)
        except Exception as e:
            logger.error(f"飞书卡片回调解析异常: {e}", exc_info=True)
        return resp


# ── MessageCard 构建器 ────────────────────────────────────────────────

def _build_feishu_card(card: OutgoingCard) -> Dict:
    """将通用 OutgoingCard 渲染为飞书 MessageCard JSON"""
    elements = []

    # 正文（Markdown）
    if card.content:
        elements.append({
            "tag": "div",
            "text": {"tag": "lark_md", "content": card.content}
        })

    # 分隔线 + 交互区（form 优先，其次 input_field，其次 buttons）
    if card.form or card.input_field or card.buttons:
        elements.append({"tag": "hr"})

    # 多输入框表单（飞书 form 容器，一次提交获取所有字段值）
    if card.form:
        f = card.form
        form_elements = []
        for ff in f.fields:
            input_elem = {
                "tag": "input",
                "name": ff.name,
                "placeholder": {"tag": "plain_text", "content": ff.placeholder},
            }
            if ff.label:
                input_elem["label"] = {"tag": "plain_text", "content": ff.label}
            form_elements.append(input_elem)
        # 提交按钮放在 form 内
        form_elements.append({
            "tag": "button",
            "text": {"tag": "plain_text", "content": f.submit_label},
            "type": "primary",
            "action_type": "form_submit",
            "value": {"action": f.submit_action, **f.submit_data},
        })
        elements.append({
            "tag": "form",
            "name": "alert_form",
            "elements": form_elements,
        })

    # 单输入框（用户按 Enter 触发回调，无需额外按钮）
    elif card.input_field:
        f = card.input_field
        elements.append({
            "tag": "action",
            "actions": [
                {
                    "tag": "input",
                    "name": f.name,
                    "placeholder": {"tag": "plain_text", "content": f.placeholder},
                }
            ]
        })

    # 按钮行（无 input_field 时渲染）
    elif card.buttons:
        btn_style_map = {
            "primary": "primary",
            "danger": "danger",
            "default": "default"
        }
        # 每行最多3个按钮，超出自动换行
        for i in range(0, len(card.buttons), 3):
            chunk = card.buttons[i:i + 3]
            actions = []
            for btn in chunk:
                actions.append({
                    "tag": "button",
                    "text": {"tag": "plain_text", "content": btn.label},
                    "type": btn_style_map.get(btn.style, "default"),
                    "value": {"action": btn.action, **btn.data}
                })
            elements.append({"tag": "action", "actions": actions})

    # 页脚
    if card.footer:
        elements.append({"tag": "hr"})
        elements.append({
            "tag": "note",
            "elements": [{"tag": "plain_text", "content": card.footer}]
        })

    return {
        "config": {"wide_screen_mode": True},
        "header": {
            "title": {"tag": "plain_text", "content": card.title},
            "template": "blue"
        },
        "elements": elements
    }
