#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Alpha Vantage 数据源封装

负责内容：汇率、大宗商品、美股新闻情绪、宏观经济指标
限制：免费版 25次/天，5次/分钟
策略：
  - 内置请求限速（≥12s 间隔保证 5次/分钟）
  - 本地内存缓存（FX/商品1小时，新闻6小时，宏观24小时）
  - 配额耗尽（返回 Note/Information 字段）时返回 None，不抛异常
"""

import logging
import time
from datetime import datetime, timedelta
from threading import Lock
from typing import Dict, List, Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────────────────

def _get_config():
    try:
        import config as cfg
        return cfg
    except ImportError:
        return None

def _api_key() -> str:
    cfg = _get_config()
    return getattr(cfg, "ALPHA_VANTAGE_API_KEY", "")

def _base_url() -> str:
    cfg = _get_config()
    return getattr(cfg, "ALPHA_VANTAGE_BASE_URL", "https://www.alphavantage.co/query")

# ── 限速 ──────────────────────────────────────────────────────────────

_rate_lock = Lock()
_last_request_time: float = 0.0
_MIN_INTERVAL = 12.0  # 秒，保证 5次/分钟上限

def _throttled_get(params: Dict) -> Optional[Dict]:
    """带限速的 GET 请求，失败或配额耗尽返回 None"""
    global _last_request_time

    key = _api_key()
    if not key or key.startswith("YOUR_"):
        logger.warning("Alpha Vantage API Key 未配置")
        return None

    with _rate_lock:
        wait = _MIN_INTERVAL - (time.time() - _last_request_time)
        if wait > 0:
            time.sleep(wait)
        _last_request_time = time.time()

    params["apikey"] = key
    try:
        resp = requests.get(_base_url(), params=params, timeout=10)
        data = resp.json()
    except Exception as e:
        logger.error(f"Alpha Vantage 请求失败: {e}")
        return None

    # 配额耗尽或无效 key 的信号
    if "Note" in data or "Information" in data:
        msg = data.get("Note") or data.get("Information", "")
        logger.warning(f"Alpha Vantage 配额/限制提示: {msg[:120]}")
        return None

    return data

# ── 内存缓存 ──────────────────────────────────────────────────────────

_cache: Dict[str, Tuple[datetime, object]] = {}

def _cached(key: str, ttl_seconds: int, fetch_fn):
    """读缓存，过期则调 fetch_fn 刷新"""
    if key in _cache:
        ts, val = _cache[key]
        if datetime.now() - ts < timedelta(seconds=ttl_seconds):
            return val
    val = fetch_fn()
    if val is not None:
        _cache[key] = (datetime.now(), val)
    return val

# ── 汇率 ──────────────────────────────────────────────────────────────

# 常用货币对预设
FOREX_PAIRS = [
    ("USD", "CNY", "美元/人民币"),
    ("EUR", "USD", "欧元/美元"),
    ("JPY", "CNY", "日元/人民币"),
    ("HKD", "CNY", "港元/人民币"),
]

def get_fx_rate(from_currency: str, to_currency: str) -> Optional[Dict]:
    """
    获取实时汇率
    返回: {"from": "USD", "to": "CNY", "rate": 7.24, "name": "美元/人民币",
           "bid": 7.23, "ask": 7.25, "updated": "2024-05-03 12:00:00"}
    """
    cache_key = f"fx_{from_currency}_{to_currency}"

    def fetch():
        data = _throttled_get({
            "function": "CURRENCY_EXCHANGE_RATE",
            "from_currency": from_currency,
            "to_currency": to_currency,
        })
        if not data:
            return None
        info = data.get("Realtime Currency Exchange Rate", {})
        if not info:
            return None
        try:
            return {
                "from": from_currency,
                "to": to_currency,
                "name": f"{from_currency}/{to_currency}",
                "rate": float(info.get("5. Exchange Rate", 0)),
                "bid": float(info.get("8. Bid Price", 0)),
                "ask": float(info.get("9. Ask Price", 0)),
                "updated": info.get("6. Last Refreshed", ""),
            }
        except (ValueError, KeyError) as e:
            logger.error(f"解析汇率数据失败 {from_currency}/{to_currency}: {e}")
            return None

    return _cached(cache_key, 3600, fetch)  # 缓存1小时


def get_fx_rates_batch(pairs: List[Tuple[str, str, str]] = None) -> List[Dict]:
    """
    批量获取多个货币对汇率（注意：AV 不支持批量，每对单独请求）
    pairs: [(from, to, display_name), ...]，默认使用 FOREX_PAIRS
    """
    pairs = pairs or FOREX_PAIRS
    results = []
    for from_c, to_c, display_name in pairs:
        r = get_fx_rate(from_c, to_c)
        if r:
            r["name"] = display_name
            results.append(r)
    return results

# ── 大宗商品 ──────────────────────────────────────────────────────────

# 支持的商品及 AV function 名
COMMODITY_MAP = {
    "WTI":          ("WTI",          "WTI原油",   "桶"),
    "BRENT":        ("BRENT",        "布伦特原油", "桶"),
    "NATURAL_GAS":  ("NATURAL_GAS",  "天然气",    "百万英热"),
    "COPPER":       ("COPPER",       "铜",        "磅"),
    "ALUMINUM":     ("ALUMINUM",     "铝",        "磅"),
    "WHEAT":        ("WHEAT",        "小麦",      "蒲式耳"),
    "CORN":         ("CORN",         "玉米",      "蒲式耳"),
    "COTTON":       ("COTTON",       "棉花",      "磅"),
    "SUGAR":        ("SUGAR",        "糖",        "磅"),
    "COFFEE":       ("COFFEE",       "咖啡",      "磅"),
    "ALL_COMMODITIES": ("ALL_COMMODITIES", "大宗商品指数", ""),
}

def get_commodity_price(commodity: str = "WTI") -> Optional[Dict]:
    """
    获取大宗商品最新价格（月度数据，取最新一条）
    返回: {"name": "WTI原油", "commodity": "WTI", "price": 82.3,
           "unit": "桶", "date": "2024-04-30", "change_pct": -0.5}
    """
    commodity = commodity.upper()
    if commodity not in COMMODITY_MAP:
        logger.warning(f"不支持的商品: {commodity}")
        return None

    func_name, display_name, unit = COMMODITY_MAP[commodity]
    cache_key = f"commodity_{commodity}"

    def fetch():
        data = _throttled_get({
            "function": func_name,
            "interval": "monthly",
        })
        if not data:
            return None
        series = data.get("data", [])
        if not series:
            return None
        # 取最新两条计算涨跌
        latest = series[0]
        prev = series[1] if len(series) > 1 else None
        try:
            price = float(latest.get("value", 0) or 0)
            prev_price = float(prev.get("value", 0) or 0) if prev else price
            change_pct = round((price - prev_price) / prev_price * 100, 2) if prev_price else 0.0
            return {
                "commodity": commodity,
                "name": display_name,
                "price": price,
                "unit": unit,
                "date": latest.get("date", ""),
                "change_pct": change_pct,
            }
        except (ValueError, ZeroDivisionError) as e:
            logger.error(f"解析商品数据失败 {commodity}: {e}")
            return None

    return _cached(cache_key, 3600, fetch)  # 缓存1小时


def get_commodities_batch(commodities: List[str] = None) -> List[Dict]:
    """批量获取大宗商品，默认取 WTI 和 BRENT"""
    commodities = commodities or ["WTI", "BRENT"]
    results = []
    for c in commodities:
        r = get_commodity_price(c)
        if r:
            results.append(r)
    return results

# ── 美股新闻情绪 ──────────────────────────────────────────────────────

def get_news_sentiment(tickers: List[str] = None,
                       topics: List[str] = None,
                       limit: int = 10) -> Optional[List[Dict]]:
    """
    获取美股新闻情绪分析
    tickers: 股票代码列表，如 ["AAPL", "NVDA"]；为 None 则获取全市场热点
    topics:  话题过滤，如 ["earnings", "technology", "economy_monetary"]
    返回: [{"title": ..., "url": ..., "source": ..., "time": ...,
             "sentiment": "Bullish/Neutral/Bearish", "score": 0.35,
             "tickers": [...]}]
    """
    cache_key = f"news_{'_'.join(sorted(tickers or []))}_{limit}"

    def fetch():
        params = {
            "function": "NEWS_SENTIMENT",
            "limit": str(limit),
            "sort": "RELEVANCE",
        }
        if tickers:
            params["tickers"] = ",".join(tickers)
        if topics:
            params["topics"] = ",".join(topics)

        data = _throttled_get(params)
        if not data:
            return None

        feed = data.get("feed", [])
        if not feed:
            return None

        results = []
        for item in feed:
            # 提取情绪得分
            overall = item.get("overall_sentiment_label", "Neutral")
            score = float(item.get("overall_sentiment_score", 0))

            # 提取相关 ticker
            ticker_sentiments = item.get("ticker_sentiment", [])
            related_tickers = [t["ticker"] for t in ticker_sentiments[:3]]

            results.append({
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "source": item.get("source", ""),
                "time": item.get("time_published", "")[:16],  # YYYYMMDDTHHmm
                "sentiment": overall,
                "score": round(score, 3),
                "tickers": related_tickers,
                "summary": item.get("summary", "")[:200],
            })
        return results

    return _cached(cache_key, 21600, fetch)  # 缓存6小时


# ── 宏观经济指标 ──────────────────────────────────────────────────────

MACRO_INDICATORS = {
    "REAL_GDP":             ("REAL_GDP",             "实际GDP",      "十亿美元", "annual"),
    "CPI":                  ("CPI",                  "CPI通胀",      "",         "monthly"),
    "INFLATION":            ("INFLATION",             "通胀率",       "%",        "annual"),
    "FEDERAL_FUNDS_RATE":   ("FEDERAL_FUNDS_RATE",   "联邦基金利率", "%",        "monthly"),
    "UNEMPLOYMENT":         ("UNEMPLOYMENT",          "失业率",       "%",        "monthly"),
    "NONFARM_PAYROLL":      ("NONFARM_PAYROLL",       "非农就业",     "千人",     "monthly"),
    "TREASURY_YIELD":       ("TREASURY_YIELD",        "10年期国债收益率", "%",    "daily"),
}

def get_macro_indicator(indicator: str) -> Optional[Dict]:
    """
    获取宏观经济指标最新值
    返回: {"name": "联邦基金利率", "indicator": "FEDERAL_FUNDS_RATE",
           "value": 5.33, "unit": "%", "date": "2024-04-30",
           "prev_value": 5.33, "change": 0.0}
    """
    indicator = indicator.upper()
    if indicator not in MACRO_INDICATORS:
        logger.warning(f"不支持的宏观指标: {indicator}")
        return None

    func_name, display_name, unit, interval = MACRO_INDICATORS[indicator]
    cache_key = f"macro_{indicator}"

    def fetch():
        params = {"function": func_name}
        if interval and indicator not in ("REAL_GDP", "INFLATION", "NONFARM_PAYROLL"):
            params["interval"] = interval

        data = _throttled_get(params)
        if not data:
            return None

        series = data.get("data", [])
        if not series:
            return None

        latest = series[0]
        prev = series[1] if len(series) > 1 else None
        try:
            value = float(latest.get("value", 0) or 0)
            prev_value = float(prev.get("value", 0) or 0) if prev else value
            return {
                "indicator": indicator,
                "name": display_name,
                "value": value,
                "unit": unit,
                "date": latest.get("date", ""),
                "prev_value": prev_value,
                "change": round(value - prev_value, 4),
            }
        except (ValueError, KeyError) as e:
            logger.error(f"解析宏观指标失败 {indicator}: {e}")
            return None

    return _cached(cache_key, 86400, fetch)  # 缓存24小时


def get_macro_summary() -> List[Dict]:
    """获取核心宏观指标摘要（联邦利率、CPI、失业率、10年期国债）"""
    targets = ["FEDERAL_FUNDS_RATE", "CPI", "UNEMPLOYMENT", "TREASURY_YIELD"]
    results = []
    for ind in targets:
        r = get_macro_indicator(ind)
        if r:
            results.append(r)
    return results


# ── 工具函数 ──────────────────────────────────────────────────────────

def clear_cache(key_prefix: str = None) -> None:
    """清除缓存，可按前缀清除特定类型"""
    global _cache
    if key_prefix is None:
        _cache.clear()
    else:
        _cache = {k: v for k, v in _cache.items() if not k.startswith(key_prefix)}


def is_configured() -> bool:
    """检查 API Key 是否已配置"""
    key = _api_key()
    return bool(key) and not key.startswith("YOUR_")
