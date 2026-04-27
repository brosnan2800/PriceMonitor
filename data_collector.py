#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数据采集模块 - 从Alpha Vantage API获取金融数据
支持：USD/CNH汇率，布伦特原油价格
"""

import requests
import time
import json
import logging
from typing import Dict, Optional, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class AlphaVantageCollector:
    """Alpha Vantage API数据收集器"""

    def __init__(self, api_key: str, request_interval: float = 2):
        """
        初始化Alpha Vantage收集器

        Args:
            api_key: Alpha Vantage API密钥
            request_interval: 两次API调用之间的间隔秒数
        """
        self.api_key = api_key
        self.base_url = "https://www.alphavantage.co/query"
        self.request_interval = request_interval

        # 上一次的价格数据，用于计算涨跌幅
        self.last_prices = {}

    def get_usd_cnh_rate(self) -> Dict:
        """
        获取USD/CNH汇率

        Returns:
            Dict: 包含汇率数据的字典，格式：
            {
                'timestamp': '2024-01-01 12:00:00',
                'price': 7.1234,
                'change': 0.01,  # 绝对值变化
                'change_percent': 0.15,  # 百分比变化
                'high': 7.13,    # 当日最高
                'low': 7.11,     # 当日最低
                'source': 'Alpha Vantage'
            }
        """
        try:
            params = {
                "function": "CURRENCY_EXCHANGE_RATE",
                "from_currency": "USD",
                "to_currency": "CNH",
                "apikey": self.api_key
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "Realtime Currency Exchange Rate" not in data:
                logger.error(f"获取USD/CNH汇率失败: {data}")
                return None

            rate_data = data["Realtime Currency Exchange Rate"]

            # 提取关键数据
            price = float(rate_data.get("5. Exchange Rate", 0))
            timestamp = rate_data.get("6. Last Refreshed", "")
            high = float(rate_data.get("8. Bid Price", price))
            low = float(rate_data.get("9. Ask Price", price))

            # 计算涨跌幅
            change = 0
            change_percent = 0
            last_price = self.last_prices.get("USD/CNH")

            if last_price and last_price["price"] > 0:
                change = price - last_price["price"]
                change_percent = (change / last_price["price"]) * 100

            result = {
                "asset": "USD/CNH",
                "timestamp": timestamp,
                "price": round(price, 4),
                "change": round(change, 4),
                "change_percent": round(change_percent, 2),
                "high": round(high, 4),
                "low": round(low, 4),
                "source": "Alpha Vantage"
            }

            # 保存当前价格
            self.last_prices["USD/CNH"] = result

            logger.info(f"USD/CNH汇率获取成功: {price}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求异常: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"数据处理异常: {e}")
            return None

    def get_brent_oil_price(self) -> Dict:
        """
        获取布伦特原油价格（使用 Alpha Vantage BRENT commodity 接口）
        """
        try:
            params = {
                "function": "BRENT",
                "interval": "daily",
                "apikey": self.api_key
            }

            response = requests.get(self.base_url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "data" not in data or not data["data"]:
                logger.error(f"获取原油价格失败: {data}")
                return None

            latest = data["data"][0]
            price = float(latest.get("value", 0))
            timestamp = latest.get("date", datetime.now().strftime("%Y-%m-%d"))

            # 计算相对于上次的变化
            change = 0.0
            change_percent = 0.0
            last_price = self.last_prices.get("BRENT_OIL")
            if last_price and last_price["price"] > 0:
                change = round(price - last_price["price"], 2)
                change_percent = round((change / last_price["price"]) * 100, 2)

            result = {
                "asset": "布伦特原油",
                "timestamp": timestamp,
                "price": round(price, 2),
                "change": change,
                "change_percent": change_percent,
                "high": round(price, 2),
                "low": round(price, 2),
                "source": "Alpha Vantage"
            }

            self.last_prices["BRENT_OIL"] = result
            logger.info(f"布伦特原油价格获取成功: ${price}")
            return result

        except requests.exceptions.RequestException as e:
            logger.error(f"网络请求异常: {e}")
            return None
        except (ValueError, KeyError) as e:
            logger.error(f"数据处理异常: {e}")
            return None

    def get_all_prices(self) -> Dict[str, Dict]:
        """
        获取所有监控资产的价格

        Returns:
            Dict: 包含所有资产价格的字典
        """
        results = {}

        # 获取USD/CNH
        usd_cnh = self.get_usd_cnh_rate()
        if usd_cnh:
            results["USD/CNH"] = usd_cnh

        # 两次API调用之间等待，避免触发频率限制
        time.sleep(self.request_interval)

        # 获取布伦特原油
        brent_oil = self.get_brent_oil_price()
        if brent_oil:
            results["布伦特原油"] = brent_oil

        return results

    def check_price_alerts(self, price_data: Dict, thresholds: Dict) -> list:
        """
        检查价格是否触发提醒阈值

        Args:
            price_data: 价格数据字典
            thresholds: 阈值配置字典

        Returns:
            list: 提醒消息列表，如果没有触发则返回空列表
        """
        alerts = []
        asset = price_data.get("asset", "")
        price = price_data.get("price", 0)
        change_percent = price_data.get("change_percent", 0)

        if asset == "USD/CNH":
            upper = thresholds.get("usd_cnh_upper", 7.15)
            lower = thresholds.get("usd_cnh_lower", 7.10)

            if price > upper:
                alerts.append(f"⚠️ USD/CNH 上涨超过阈值: {price} > {upper}")
            elif price < lower:
                alerts.append(f"⚠️ USD/CNH 下跌超过阈值: {price} < {lower}")

        elif asset == "布伦特原油":
            change_threshold = thresholds.get("oil_change_percent", 1.0)

            if abs(change_percent) > change_threshold:
                direction = "上涨" if change_percent > 0 else "下跌"
                alerts.append(f"⚠️ 布伦特原油 {direction} {abs(change_percent)}%，超过阈值 {change_threshold}%")

        return alerts


def test_alpha_vantage():
    """测试Alpha Vantage API"""
    import os
    from dotenv import load_dotenv

    load_dotenv()

    api_key = os.getenv("ALPHA_VANTAGE_API_KEY")
    if not api_key:
        print("请设置 ALPHA_VANTAGE_API_KEY 环境变量")
        return

    collector = AlphaVantageCollector(api_key)

    print("=== 测试Alpha Vantage API ===")

    # 测试USD/CNH
    print("获取USD/CNH汇率...")
    usd_cnh = collector.get_usd_cnh_rate()
    if usd_cnh:
        print(f"USD/CNH: {usd_cnh}")
    else:
        print("USD/CNH获取失败")

    # 测试布伦特原油
    print("获取布伦特原油价格...")
    oil_price = collector.get_brent_oil_price()
    if oil_price:
        print(f"布伦特原油: {oil_price}")
    else:
        print("布伦特原油获取失败")

    # 测试阈值提醒
    if usd_cnh:
        thresholds = {
            "usd_cnh_upper": 7.15,
            "usd_cnh_lower": 7.10,
            "oil_change_percent": 1.0
        }
        alerts = collector.check_price_alerts(usd_cnh, thresholds)
        for alert in alerts:
            print(f"提醒: {alert}")


if __name__ == "__main__":
    # 设置基础日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    test_alpha_vantage()