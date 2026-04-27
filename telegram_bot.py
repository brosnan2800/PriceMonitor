#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram机器人推送模块
用于发送价格监控消息到Telegram
"""

import requests
import logging
from typing import Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class TelegramBot:
    """Telegram机器人推送类"""

    def __init__(self, bot_token: str, chat_id: str):
        """
        初始化Telegram机器人

        Args:
            bot_token: Telegram Bot Token
            chat_id: Telegram Chat ID（用户或群组的ID）
        """
        self.bot_token = bot_token
        self.chat_id = chat_id
        self.base_url = f"https://api.telegram.org/bot{bot_token}"

    def send_message(self, text: str, parse_mode: str = "Markdown",
                    disable_web_page_preview: bool = True) -> bool:
        """
        发送文本消息到Telegram

        Args:
            text: 消息文本（支持Markdown格式）
            parse_mode: 解析模式，可选 "Markdown" 或 "HTML"
            disable_web_page_preview: 是否禁用链接预览

        Returns:
            bool: 发送是否成功
        """
        try:
            url = f"{self.base_url}/sendMessage"
            payload = {
                "chat_id": self.chat_id,
                "text": text,
                "parse_mode": parse_mode,
                "disable_web_page_preview": disable_web_page_preview
            }

            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                logger.info(f"Telegram消息发送成功: {text[:50]}...")
                return True
            else:
                logger.error(f"Telegram消息发送失败: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"发送Telegram消息网络异常: {e}")
            return False
        except Exception as e:
            logger.error(f"发送Telegram消息异常: {e}")
            return False

    def format_price_message(self, price_data: Dict[str, Dict],
                           alerts: List[str] = None,
                           next_check_time: str = None) -> str:
        """
        格式化价格信息为Telegram消息

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
        message = "📈 *价格监控报告* 📈\n\n"

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

            # 格式化数字
            if abs(change_percent) >= 0.01:
                change_percent_str = f"{trend_sign}{abs(change_percent)}%"
            else:
                change_percent_str = "0%"

            # 添加到消息
            message += f"{asset_emoji} *{asset_name}*\n"
            message += f"    └─ 价格: `{price}{unit}`\n"

            if change != 0:
                message += f"    └─ 涨跌: {trend_emoji} `{change_percent_str}` "
                message += f"(`{trend_sign}{abs(change)}{unit}`)\n"

            message += f"    └─ 时间: {timestamp}\n\n"

        # 添加提醒设置
        if alerts:
            message += "⚠️ *触发提醒* ⚠️\n"
            for alert in alerts:
                message += f"• {alert}\n"
            message += "\n"

        # 添加系统信息
        message += "🔧 *系统信息*\n"
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
        alert_message = f"🚨 *价格警报* 🚨\n\n{alert_text}"
        return self.send_message(alert_message)

    def send_daily_summary(self, daily_prices: List[Dict]) -> bool:
        """
        发送每日汇总报告

        Args:
            daily_prices: 每日价格数据列表

        Returns:
            bool: 发送是否成功
        """
        if not daily_prices:
            return False

        # 计算当日的开盘、收盘、最高、最低
        summary = {}
        for entry in daily_prices:
            for asset_name, data in entry.items():
                if asset_name not in summary:
                    summary[asset_name] = {
                        "prices": [],
                        "timestamps": []
                    }
                summary[asset_name]["prices"].append(data.get("price", 0))
                summary[asset_name]["timestamps"].append(data.get("timestamp", ""))

        today = datetime.now().strftime("%Y-%m-%d")
        message = f"📊 *每日价格汇总* ({today})\n\n"

        for asset_name, data in summary.items():
            prices = data["prices"]
            if not prices:
                continue

            opening = prices[0]
            closing = prices[-1]
            highest = max(prices)
            lowest = min(prices)
            change = closing - opening
            change_percent = (change / opening * 100) if opening > 0 else 0

            trend_emoji = "📈" if change > 0 else "📉" if change < 0 else "➡️"
            change_sign = "+" if change > 0 else ""

            message += f"*{asset_name}*\n"
            message += f"└─ 开盘: `{opening}`\n"
            message += f"└─ 收盘: `{closing}`\n"
            message += f"└─ 最高: `{highest}`\n"
            message += f"└─ 最低: `{lowest}`\n"
            message += f"└─ 涨跌: {trend_emoji} `{change_sign}{change_percent:.2f}%`\n\n"

        message += "*数据来源*: Alpha Vantage API"

        return self.send_message(message)

    def test_connection(self) -> bool:
        """
        测试Telegram连接

        Returns:
            bool: 连接是否成功
        """
        try:
            url = f"{self.base_url}/getMe"
            response = requests.get(url, timeout=5)
            response.raise_for_status()

            result = response.json()
            if result.get("ok"):
                bot_info = result.get("result", {})
                logger.info(f"Telegram Bot连接成功: @{bot_info.get('username')}")
                return True
            else:
                logger.error(f"Telegram Bot连接测试失败: {result}")
                return False

        except requests.exceptions.RequestException as e:
            logger.error(f"Telegram连接测试网络异常: {e}")
            return False


def test_telegram_bot():
    """测试Telegram Bot功能"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")

    if not bot_token or not chat_id:
        print("请设置 TELEGRAM_BOT_TOKEN 和 TELEGRAM_CHAT_ID 环境变量")
        return

    # 创建机器人实例
    bot = TelegramBot(bot_token, chat_id)

    print("=== 测试Telegram Bot ===")

    # 测试连接
    print("测试连接...")
    if not bot.test_connection():
        print("连接失败，请检查Token和Chat ID")
        return
    print("连接成功！")

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

    print("测试完成，请检查Telegram消息")


if __name__ == "__main__":
    # 设置基础日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_telegram_bot()