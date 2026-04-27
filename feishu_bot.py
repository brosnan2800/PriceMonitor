#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人推送模块
用于发送价格监控消息到飞书群聊或用户

飞书开放平台文档参考：https://open.feishu.cn/document/ukTMukTMukTM/ucjNz4iN3MjLyczY
"""

import requests
import logging
import time
import json
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class FeishuBot:
    """飞书机器人推送类"""

    # 飞书API端点
    AUTH_URL = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    SEND_MESSAGE_URL = "https://open.feishu.cn/open-apis/im/v1/messages"
    GET_CHATS_URL = "https://open.feishu.cn/open-apis/im/v1/chats"

    def __init__(self, app_id: str, app_secret: str, chat_id: str = None, open_id: str = None):
        """
        初始化飞书机器人

        Args:
            app_id: 飞书开放平台应用 ID
            app_secret: 飞书开放平台应用密钥
            chat_id: 飞书群聊 ID（群聊推送用）
            open_id: 用户 open_id（私聊推送用，由 feishu_setup.py 扫码获取）
        """
        self.app_id = app_id
        self.app_secret = app_secret
        self.chat_id = chat_id
        self.open_id = open_id  # 私聊目标
        self.tenant_access_token = None
        self.token_expire_time = 0

    def get_tenant_access_token(self) -> Optional[str]:
        """
        获取租户访问令牌 (tenant_access_token)

        Returns:
            str: 访问令牌，失败返回 None
        """
        # 如果令牌未过期，直接返回缓存的令牌
        if self.tenant_access_token and time.time() < self.token_expire_time:
            return self.tenant_access_token

        try:
            payload = {
                "app_id": self.app_id,
                "app_secret": self.app_secret
            }

            response = requests.post(self.AUTH_URL, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 0:
                self.tenant_access_token = result.get("tenant_access_token")
                # 令牌有效期通常为2小时，这里设置为1小时50分钟避免边界问题
                self.token_expire_time = time.time() + 6600
                logger.info("飞书 tenant_access_token 获取成功")
                return self.tenant_access_token
            else:
                logger.error(f"飞书 token 获取失败: {result}")
                return None

        except requests.exceptions.RequestException as e:
            logger.error(f"获取飞书 token 网络异常: {e}")
            return None
        except Exception as e:
            logger.error(f"获取飞书 token 异常: {e}")
            return None

    def _ensure_token(self) -> bool:
        """确保有有效的访问令牌"""
        if not self.tenant_access_token or time.time() >= self.token_expire_time:
            return self.get_tenant_access_token() is not None
        return True

    def send_message(self, text: str, chat_id: str = None,
                    msg_type: str = "text", **kwargs) -> bool:
        """
        发送文本消息到飞书。

        优先级：
          1. 参数传入的 chat_id（群聊）
          2. 初始化时的 open_id（私聊，receive_id_type=open_id）
          3. 初始化时的 chat_id（群聊，receive_id_type=chat_id）
        """
        target_id = chat_id or self.open_id or self.chat_id
        if not target_id:
            logger.error("未配置飞书接收者（open_id 或 chat_id），无法发送消息")
            return False

        # 判断 receive_id_type
        if chat_id:
            receive_id_type = "chat_id"
        elif self.open_id and not chat_id:
            receive_id_type = "open_id"
        else:
            receive_id_type = "chat_id"

        if not self._ensure_token():
            logger.error("无法获取飞书访问令牌，消息发送失败")
            return False

        try:
            headers = {
                "Authorization": f"Bearer {self.tenant_access_token}",
                "Content-Type": "application/json; charset=utf-8"
            }

            content = {"text": text}

            payload = {
                "receive_id": target_id,
                "msg_type": "text",
                "content": json.dumps(content, ensure_ascii=False)
            }

            response = requests.post(
                self.SEND_MESSAGE_URL,
                headers=headers,
                json=payload,
                params={"receive_id_type": receive_id_type},
                timeout=10
            )
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 0:
                logger.info(f"飞书消息发送成功: {text[:50]}...")
                return True
            else:
                logger.error(f"飞书消息发送失败: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"发送飞书消息网络异常: {e}")
            return False
        except Exception as e:
            logger.error(f"发送飞书消息异常: {e}")
            return False

    def format_price_message(self, price_data: Dict[str, Dict],
                           alerts: List[str] = None,
                           next_check_time: str = None) -> str:
        """
        格式化价格信息为飞书消息

        Args:
            price_data: 价格数据字典
            alerts: 提醒消息列表
            next_check_time: 下次检查时间

        Returns:
            str: 格式化后的消息文本
        """
        if alerts is None:
            alerts = []

        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 开始构建消息
        message = "📈 价格监控报告 📈\n\n"

        # 添加每种资产的价格信息
        for asset_name, data in price_data.items():
            price = data.get("price", 0)
            change = data.get("change", 0)
            change_percent = data.get("change_percent", 0)
            timestamp = data.get("timestamp", current_time)

            # 确定涨跌符号和表情
            if change > 0:
                trend_emoji = "📈"
                trend_sign = "+"
            elif change < 0:
                trend_emoji = "📉"
                trend_sign = "-"
            else:
                trend_emoji = "➡️"
                trend_sign = ""

            # 根据资产类型选择图标
            if "USD" in asset_name or "CNH" in asset_name:
                asset_emoji = "💰"
                unit = ""
            elif "原油" in asset_name:
                asset_emoji = "🛢️"
                unit = "美元/桶"
            else:
                asset_emoji = "📊"
                unit = ""

            # 添加到消息
            message += f"{asset_emoji} {asset_name}\n"
            message += f"    价格: {price}{unit}\n"

            if change != 0:
                message += f"    涨跌: {trend_emoji} {trend_sign}{abs(change_percent)}% "
                message += f"({trend_sign}{abs(change)}{unit})\n"

            message += f"    时间: {timestamp}\n\n"

        # 添加提醒设置
        if alerts:
            message += "⚠️ 触发提醒 ⚠️\n"
            for alert in alerts:
                message += f"• {alert}\n"
            message += "\n"

        # 添加系统信息
        message += "🔧 系统信息\n"
        message += f"• 本次检查: {current_time}\n"
        if next_check_time:
            message += f"• 下次检查: {next_check_time}\n"

        return message

    def send_price_report(self, price_data: Dict[str, Dict],
                         alerts: List[str] = None,
                         next_check_time: str = None) -> bool:
        """
        发送价格报告

        Args:
            price_data: 价格数据字典
            alerts: 提醒消息列表
            next_check_time: 下次检查时间

        Returns:
            bool: 发送是否成功
        """
        if not price_data:
            logger.warning("没有价格数据可发送")
            return False

        # 格式化消息
        message = self.format_price_message(price_data, alerts, next_check_time)

        # 发送消息
        return self.send_message(message)

    def send_alert(self, alert_text: str) -> bool:
        """
        发送紧急提醒消息

        Args:
            alert_text: 提醒文本

        Returns:
            bool: 发送是否成功
        """
        alert_message = f"🚨 价格警报 🚨\n\n{alert_text}"
        return self.send_message(alert_message)

    def test_connection(self) -> bool:
        """
        测试飞书连接

        Returns:
            bool: 连接是否成功
        """
        try:
            if not self._ensure_token():
                logger.error("无法获取飞书访问令牌")
                return False

            logger.info("飞书连接测试成功")
            return True

        except Exception as e:
            logger.error(f"飞书连接测试异常: {e}")
            return False

    def get_chat_list(self) -> Optional[List[Dict]]:
        """
        获取机器人所在的群聊列表

        Returns:
            list: 群聊列表，失败返回 None
        """
        if not self._ensure_token():
            logger.error("无法获取飞书访问令牌")
            return None

        try:
            headers = {
                "Authorization": f"Bearer {self.tenant_access_token}",
                "Content-Type": "application/json"
            }

            response = requests.get(self.GET_CHATS_URL, headers=headers, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("code") == 0:
                chats = result.get("data", {}).get("items", [])
                logger.info(f"获取到 {len(chats)} 个群聊")
                return chats
            else:
                logger.error(f"获取群聊列表失败: {result}")
                return None

        except Exception as e:
            logger.error(f"获取群聊列表异常: {e}")
            return None

    def send_daily_summary(self, daily_prices: List[Dict]) -> bool:
        """
        发送每日汇总报告（飞书暂不支持，提供占位实现）

        Args:
            daily_prices: 每日价格数据列表

        Returns:
            bool: 发送是否成功（目前始终返回False）
        """
        # 飞书机器人暂不支持每日汇总功能
        # 可以未来实现，目前返回False表示不支持
        logger.warning("飞书机器人暂不支持每日汇总功能")
        return False


def test_feishu_bot():
    """测试飞书 Bot 功能"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # 优先从 config.py 读取
    try:
        import config
        app_id = getattr(config, "FEISHU_APP_ID", None) or os.getenv("FEISHU_APP_ID")
        app_secret = getattr(config, "FEISHU_APP_SECRET", None) or os.getenv("FEISHU_APP_SECRET")
        chat_id = getattr(config, "FEISHU_CHAT_ID", None) or os.getenv("FEISHU_CHAT_ID")
        open_id = getattr(config, "FEISHU_OPEN_ID", None) or os.getenv("FEISHU_OPEN_ID")
    except ImportError:
        app_id = os.getenv("FEISHU_APP_ID")
        app_secret = os.getenv("FEISHU_APP_SECRET")
        chat_id = os.getenv("FEISHU_CHAT_ID")
        open_id = os.getenv("FEISHU_OPEN_ID")

    if not app_id or not app_secret:
        print("❌ 未配置飞书凭证，请先运行: python feishu_setup.py")
        return

    bot = FeishuBot(app_id, app_secret, chat_id=chat_id, open_id=open_id)

    print("=== 测试飞书 Bot ===")

    print("测试连接...")
    if not bot.test_connection():
        print("❌ 连接失败，请检查 App ID 和 App Secret")
        return
    print("✅ 连接成功！")

    if not open_id and not chat_id:
        print("⚠️  未配置接收者，请先运行: python feishu_setup.py")
        chats = bot.get_chat_list()
        if chats:
            print("找到以下群聊（可填入 FEISHU_CHAT_ID）：")
            for chat in chats[:5]:
                print(f"  - {chat.get('name', '未知')}: {chat.get('chat_id')}")
        return

    # 创建测试数据
    test_price_data = {
        "USD/CNH": {
            "asset": "USD/CNH",
            "price": 7.1234,
            "change": 0.0111,
            "change_percent": 0.15,
            "timestamp": "2024-01-01 14:30:05",
            "high": 7.13,
            "low": 7.11,
            "source": "Alpha Vantage"
        },
        "布伦特原油": {
            "asset": "布伦特原油",
            "price": 85.67,
            "change": -0.36,
            "change_percent": -0.42,
            "timestamp": "2024-01-01 14:30:05",
            "high": 86.03,
            "low": 85.45,
            "source": "Alpha Vantage"
        }
    }

    test_alerts = [
        "USD/CNH 上涨超过阈值: 7.1234 > 7.10",
        "布伦特原油下跌 0.42%，超过阈值 0.5%"
    ]

    # 发送测试消息
    print("发送测试报告...")
    success = bot.send_price_report(test_price_data, test_alerts, "14:35:05")
    if success:
        print("测试消息发送成功！")
    else:
        print("测试消息发送失败")

    # 测试单独提醒
    print("发送测试警报...")
    bot.send_alert("测试警报：价格大幅波动！")

    print("测试完成，请检查飞书消息")


if __name__ == "__main__":
    # 设置基础日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_feishu_bot()