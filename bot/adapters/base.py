#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
渠道适配器抽象基类
所有 IM 平台（飞书、Telegram 等）继承此类实现各自的收发逻辑
核心业务逻辑只与 BaseAdapter 交互，不感知具体平台
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class IncomingMessage:
    """统一的入站消息格式"""
    platform: str           # 平台标识：feishu / telegram
    user_id: str            # 用户唯一ID（飞书 open_id / Telegram chat_id）
    username: str           # 用户名（展示用）
    text: str               # 消息文本（已去除前后空白）
    message_id: str         # 平台原始消息 ID
    raw: Dict               # 原始 payload（调试用）
    callback_data: Optional[str] = None   # 按钮回调数据（非按钮消息为 None）


@dataclass
class CardButton:
    """卡片按钮定义"""
    label: str              # 按钮显示文字
    action: str             # 回调 action 标识
    data: Dict = field(default_factory=dict)   # 附加数据
    style: str = "default"  # default / primary / danger


@dataclass
class CardInput:
    """卡片输入框定义（飞书交互卡片 input 组件）"""
    name: str                   # 回调 form_value 中的 key
    placeholder: str            # 占位提示文字
    action: str                 # 提交按钮的 action 标识
    submit_label: str = "确认 ✓"
    submit_style: str = "primary"


@dataclass
class CardFormField:
    """表单中的单个输入字段"""
    name: str           # 字段名（提交后在 form_value 中作为 key）
    label: str          # 字段标签文字
    placeholder: str = ""
    required: bool = False


@dataclass
class CardForm:
    """多输入框表单（飞书 form 容器，一次提交获取所有字段值）"""
    fields: List[CardFormField] = field(default_factory=list)
    submit_label: str = "确认"
    submit_action: str = ""       # 路由到哪个 handler
    submit_data: Dict = field(default_factory=dict)   # 额外附带数据（如预设 symbol）


@dataclass
class OutgoingCard:
    """平台无关的卡片消息结构（各适配器自行渲染）"""
    title: str
    content: str                                      # 正文（Markdown-like）
    buttons: List[CardButton] = field(default_factory=list)
    footer: Optional[str] = None
    input_field: Optional[CardInput] = None           # 单输入框（Enter 提交）
    form: Optional[CardForm] = None                   # 多输入框表单（按钮提交）


class BaseAdapter(ABC):
    """所有渠道适配器的抽象基类"""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """平台标识字符串，如 'feishu' / 'telegram'"""

    @abstractmethod
    def send_text(self, user_id: str, text: str) -> bool:
        """发送纯文本消息"""

    @abstractmethod
    def send_card(self, user_id: str, card: OutgoingCard) -> bool:
        """发送富交互卡片消息（飞书 MessageCard / Telegram InlineKeyboard）"""

    @abstractmethod
    def start(self, on_message) -> None:
        """
        启动平台监听（阻塞或后台线程）
        on_message: Callable[[IncomingMessage], None]
        """

    @abstractmethod
    def stop(self) -> None:
        """停止平台监听"""

    # ── 便捷方法（子类可覆盖优化） ──────────────────────────────────────

    def send_error(self, user_id: str, text: str) -> bool:
        return self.send_text(user_id, f"❌ {text}")

    def send_success(self, user_id: str, text: str) -> bool:
        return self.send_text(user_id, f"✅ {text}")
