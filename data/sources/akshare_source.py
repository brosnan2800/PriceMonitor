#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
A股数据源封装

主数据源：腾讯财经 API（HTTP，股票名称+完整行情，CDN 无 push2 依赖）
备用数据源：pytdx（通达信 TCP 协议，无 HTTP CDN 依赖，价格准确）
最终降级：AKShare（HTTP，东方财富接口，需网络条件良好）

支持：
  - A股实时行情（单支 + 全市场）
  - 沪深指数
  - 个股公告
  - 港股实时
  - 加密货币
  - 汇率（降级到 Alpha Vantage）
"""

import logging
import socket
from datetime import datetime
from typing import Dict, List, Optional

import requests

logger = logging.getLogger(__name__)

# 资产类型常量
TYPE_A_STOCK = "a_stock"
TYPE_HK_STOCK = "hk_stock"
TYPE_US_STOCK = "us_stock"
TYPE_INDEX = "index"
TYPE_FOREX = "forex"
TYPE_CRYPTO = "crypto"
TYPE_COMMODITY = "commodity"

# 腾讯财经行情 API
_TENCENT_QUOTE_URL = "http://qt.gtimg.cn/q={symbols}"

# 通达信服务器列表（TCP 7709，按可用性排序）
_TDX_SERVERS = [
    ('180.153.18.170', 7709),
    ('218.75.126.9',   7709),
    ('119.147.212.81', 7709),
    ('14.215.167.220', 7709),
]


def _lazy_akshare():
    """懒加载 akshare，避免启动时崩溃"""
    try:
        import akshare as ak
        return ak
    except ImportError:
        logger.error("缺少 akshare，请运行: pip install akshare")
        return None


def _get_tdx_market(symbol: str) -> int:
    """根据股票代码判断市场：0=深圳，1=上海"""
    return 1 if symbol.startswith("6") else 0


def _tencent_symbol(symbol: str) -> str:
    """将6位股票代码转为腾讯财经格式：sh600519 / sz000858"""
    return ("sh" if symbol.startswith("6") else "sz") + symbol


def _connect_tdx():
    """
    连接通达信服务器（优先选第一个可用的）
    返回已连接的 TdxHq_API 实例，失败返回 None
    """
    try:
        from pytdx.hq import TdxHq_API
    except ImportError:
        logger.warning("pytdx 未安装，跳过通达信数据源")
        return None

    for host, port in _TDX_SERVERS:
        try:
            s = socket.socket()
            s.settimeout(2)
            reachable = s.connect_ex((host, port)) == 0
            s.close()
            if not reachable:
                continue
        except Exception:
            continue

        try:
            api = TdxHq_API(heartbeat=False)
            if api.connect(host, port):
                return api
        except Exception as e:
            logger.debug(f"TDX connect {host}:{port} failed: {e}")

    logger.warning("所有通达信服务器均不可达")
    return None


def _parse_tencent_quote(line: str) -> Optional[Dict]:
    """
    解析腾讯财经单行响应，返回标准行情字典
    格式：v_sh600519="1~贵州茅台~600519~price~prev_close~open~vol~...~change_amt~change_pct~high~low~..."
    """
    try:
        if "~" not in line:
            return None
        inner = line.split("~")
        if len(inner) < 35:
            return None
        name = inner[1].strip().replace(" ", "")  # 腾讯返回的名称有时含空格
        code = inner[2].strip()
        price = float(inner[3]) if inner[3] else 0.0
        prev_close = float(inner[4]) if inner[4] else price
        today_open = float(inner[5]) if inner[5] else 0.0
        volume_lots = float(inner[6]) if inner[6] else 0.0    # 手（100股/手）
        change_amt = float(inner[31]) if inner[31] else 0.0
        change_pct = float(inner[32]) if inner[32] else 0.0
        high = float(inner[33]) if inner[33] else 0.0
        low = float(inner[34]) if inner[34] else 0.0
        # inner[37] 是成交额（万元）
        turnover = float(inner[37]) * 10000 if len(inner) > 37 and inner[37] else 0.0

        return {
            "symbol": code,
            "name": name,
            "asset_type": TYPE_A_STOCK,
            "price": price,
            "change": change_amt,
            "change_pct": change_pct,
            "open": today_open,
            "high": high,
            "low": low,
            "volume": volume_lots * 100,
            "turnover": turnover,
            "market_cap": 0.0,
            "pe_ratio": 0.0,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "腾讯财经"
        }
    except Exception as e:
        logger.debug(f"腾讯行情解析失败: {e}")
        return None


# ── A股实时行情 ───────────────────────────────────────────────────────

def get_stock_quote(symbol: str) -> Optional[Dict]:
    """
    获取单支A股实时行情
    主接口：腾讯财经 API（HTTP，含股票名称，不依赖 push2.eastmoney.com）
    备接口：pytdx 通达信（TCP，无 HTTP CDN 依赖）
    末备：AKShare（HTTP，东方财富）
    symbol: 6位股票代码，如 '600519'
    """
    # ── 方案A：腾讯财经（主，含名称） ──
    try:
        url = _TENCENT_QUOTE_URL.format(symbols=_tencent_symbol(symbol))
        resp = requests.get(url, timeout=5)
        resp.encoding = "gbk"
        for line in resp.text.splitlines():
            if symbol in line and "~" in line:
                result = _parse_tencent_quote(line)
                if result:
                    return result
    except Exception as e:
        logger.debug(f"腾讯财经接口失败 {symbol}: {e}")

    # ── 方案B：pytdx 通达信 ──
    api = _connect_tdx()
    if api:
        try:
            market = _get_tdx_market(symbol)
            quotes = api.get_security_quotes([(market, symbol)])
            api.disconnect()
            if quotes:
                d = quotes[0]
                price = float(d.get("price", 0) or 0)
                prev_close = float(d.get("last_close", price) or price)
                change = round(price - prev_close, 3)
                change_pct = round((change / prev_close * 100) if prev_close else 0, 2)
                return {
                    "symbol": symbol,
                    "name": symbol,  # pytdx 不直接提供股票名称
                    "asset_type": TYPE_A_STOCK,
                    "price": price,
                    "change": change,
                    "change_pct": change_pct,
                    "open": float(d.get("open", 0) or 0),
                    "high": float(d.get("high", 0) or 0),
                    "low": float(d.get("low", 0) or 0),
                    "volume": float(d.get("vol", 0) or 0) * 100,
                    "turnover": float(d.get("amount", 0) or 0),
                    "market_cap": 0.0,
                    "pe_ratio": 0.0,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "pytdx/通达信"
                }
        except Exception as e:
            logger.debug(f"pytdx 查询失败 {symbol}: {e}")
            try:
                api.disconnect()
            except Exception:
                pass

    ak = _lazy_akshare()
    if not ak:
        logger.warning(f"未找到股票: {symbol}")
        return None

    # ── 方案C：AKShare 分时成交接口 ──
    try:
        df = ak.stock_intraday_em(symbol=symbol)
        if df is not None and not df.empty:
            last = df.iloc[-1]
            price = float(last.get("成交价", 0) or 0)
            name = symbol
            prev_close = price
            try:
                info_df = ak.stock_individual_info_em(symbol=symbol)
                info = dict(zip(info_df["item"], info_df["value"]))
                name = str(info.get("股票简称", symbol))
                if len(df) > 1:
                    first_price = float(df.iloc[0].get("成交价", price) or price)
                    prev_close = first_price if first_price else price
            except Exception:
                pass
            change = round(price - prev_close, 3)
            change_pct = round((change / prev_close * 100) if prev_close else 0, 2)
            return {
                "symbol": symbol,
                "name": name,
                "asset_type": TYPE_A_STOCK,
                "price": price,
                "change": change,
                "change_pct": change_pct,
                "open": 0.0,
                "high": float(df["成交价"].max()),
                "low": float(df["成交价"].min()),
                "volume": 0.0,
                "turnover": 0.0,
                "market_cap": 0.0,
                "pe_ratio": 0.0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "AKShare/分时"
            }
    except Exception as e:
        logger.debug(f"AKShare 分时接口失败 {symbol}: {e}")

    # ── 方案D：AKShare 全市场快照 ──
    try:
        df = ak.stock_zh_a_spot_em()
        row = df[df["代码"] == symbol]
        if row.empty:
            row = df[df["代码"].str.endswith(symbol)]
        if not row.empty:
            r = row.iloc[0]
            price = float(r.get("最新价", 0) or 0)
            prev_close = float(r.get("昨收", price) or price)
            change = round(price - prev_close, 3)
            change_pct = round((change / prev_close * 100) if prev_close else 0, 2)
            return {
                "symbol": symbol,
                "name": str(r.get("名称", "")),
                "asset_type": TYPE_A_STOCK,
                "price": price,
                "change": change,
                "change_pct": change_pct,
                "open": float(r.get("今开", 0) or 0),
                "high": float(r.get("最高", 0) or 0),
                "low": float(r.get("最低", 0) or 0),
                "volume": float(r.get("成交量", 0) or 0),
                "turnover": float(r.get("成交额", 0) or 0),
                "market_cap": float(r.get("总市值", 0) or 0),
                "pe_ratio": float(r.get("市盈率-动态", 0) or 0),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "AKShare/东方财富"
            }
    except Exception as e:
        logger.debug(f"AKShare 全市场快照接口失败 {symbol}: {e}")

    logger.warning(f"未找到股票: {symbol}")
    return None


# ── 沪深指数 ──────────────────────────────────────────────────────────

# 主要指数：腾讯财经代码 → 显示名称
INDEX_MAP = {
    # A股指数（腾讯财经 sh/sz 前缀）
    "sh000001": "上证指数",
    "sz399001": "深证成指",
    "sz399006": "创业板指",
    "sh000300": "沪深300",
    "sh000016": "上证50",
    # 美股三大指数（腾讯财经 us. 前缀）
    "us.DJI":  "道琼斯",
    "us.IXIC": "纳斯达克",
    "us.INX":  "标普500",
}


def get_index_quotes() -> List[Dict]:
    """
    获取主要A股指数行情
    主接口：腾讯财经 qt.gtimg.cn（不依赖 push2.eastmoney.com）
    备接口：AKShare stock_zh_index_spot_em
    """
    # ── 方案A：腾讯财经 ──
    try:
        symbols = ",".join(INDEX_MAP.keys())
        resp = requests.get(_TENCENT_QUOTE_URL.format(symbols=symbols), timeout=5)
        resp.encoding = "gbk"
        results = []
        for line in resp.text.splitlines():
            inner = line.split("~")
            if len(inner) < 35:
                continue
            code = inner[2].strip()
            # 腾讯返回的代码：A股 "000001"，美指 ".DJI"
            # INDEX_MAP 键格式：sh000001, us.DJI
            matched_key = next(
                (k for k in INDEX_MAP if k.endswith(code) or k == "us" + code),
                None
            )
            if not matched_key:
                continue
            price = float(inner[3]) if inner[3] else 0.0
            change_amt = float(inner[31]) if inner[31] else 0.0
            change_pct = float(inner[32]) if inner[32] else 0.0
            results.append({
                "symbol": matched_key,
                "name": INDEX_MAP[matched_key],
                "asset_type": TYPE_INDEX,
                "price": price,
                "change": change_amt,
                "change_pct": change_pct,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "腾讯财经"
            })
        if results:
            return results
    except Exception as e:
        logger.debug(f"腾讯财经指数接口失败: {e}")

    # ── 方案B：AKShare ──
    ak = _lazy_akshare()
    if not ak:
        return []
    try:
        df = ak.stock_zh_index_spot_em()
        results = []
        for code, name in INDEX_MAP.items():
            short_code = code[2:]
            row = df[df["代码"] == short_code]
            if row.empty:
                continue
            r = row.iloc[0]
            results.append({
                "symbol": code,
                "name": name,
                "asset_type": TYPE_INDEX,
                "price": float(r.get("最新价", 0) or 0),
                "change": float(r.get("涨跌额", 0) or 0),
                "change_pct": float(r.get("涨跌幅", 0) or 0),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "AKShare/东方财富"
            })
        return results
    except Exception as e:
        logger.error(f"获取指数行情失败: {e}")
        return []


# ── 个股公告 ──────────────────────────────────────────────────────────

# 关注的公告类型关键词（用于过滤，避免推送无关公告）
IMPORTANT_NOTICE_KEYWORDS = [
    "年度报告", "半年度报告", "季度报告",
    "重大资产", "重组", "收购", "股权",
    "利润分配", "分红", "配股", "增发",
    "退市", "暂停上市", "风险提示",
    "重大合同", "业绩预告", "业绩快报"
]


def get_stock_announcements(symbol: str, limit: int = 5,
                             important_only: bool = True) -> List[Dict]:
    """
    获取个股最新公告
    symbol: 6位股票代码
    important_only: 仅返回重要公告（含关键词过滤）
    """
    ak = _lazy_akshare()
    if not ak:
        return []
    try:
        df = ak.stock_notice_report(symbol=symbol)
        if df is None or df.empty:
            return []

        results = []
        for _, row in df.iterrows():
            title = str(row.get("公告标题", "") or "")
            if important_only:
                if not any(kw in title for kw in IMPORTANT_NOTICE_KEYWORDS):
                    continue
            results.append({
                "symbol": symbol,
                "title": title,
                "date": str(row.get("公告日期", "") or ""),
                "url": str(row.get("公告链接", "") or ""),
            })
            if len(results) >= limit:
                break
        return results
    except Exception as e:
        logger.error(f"获取公告失败 {symbol}: {e}")
        return []


# ── 港股行情 ──────────────────────────────────────────────────────────

def get_hk_stock_quote(symbol: str) -> Optional[Dict]:
    """
    获取港股实时行情
    主接口：腾讯财经（hk00700 格式，不依赖 push2.eastmoney.com）
    备接口：AKShare stock_hk_spot_em
    symbol: 港股代码，如 '00700'（腾讯）
    """
    # ── 方案A：腾讯财经 ──
    try:
        tencent_code = "hk" + symbol.lstrip("0").zfill(5)
        resp = requests.get(_TENCENT_QUOTE_URL.format(symbols=tencent_code), timeout=5)
        resp.encoding = "gbk"
        for line in resp.text.splitlines():
            if symbol.lstrip("0") in line and "~" in line:
                inner = line.split("~")
                if len(inner) < 35:
                    continue
                name = inner[1].strip().replace(" ", "")
                price = float(inner[3]) if inner[3] else 0.0
                prev_close = float(inner[4]) if inner[4] else price
                change_amt = float(inner[31]) if inner[31] else 0.0
                change_pct = float(inner[32]) if inner[32] else 0.0
                return {
                    "symbol": symbol,
                    "name": name,
                    "asset_type": TYPE_HK_STOCK,
                    "price": price,
                    "change": change_amt,
                    "change_pct": change_pct,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "腾讯财经"
                }
    except Exception as e:
        logger.debug(f"腾讯财经港股接口失败 {symbol}: {e}")

    # ── 方案B：AKShare ──
    ak = _lazy_akshare()
    if not ak:
        return None
    try:
        df = ak.stock_hk_spot_em()
        row = df[df["代码"] == symbol]
        if row.empty:
            return None
        r = row.iloc[0]
        return {
            "symbol": symbol,
            "name": str(r.get("名称", "")),
            "asset_type": TYPE_HK_STOCK,
            "price": float(r.get("最新价", 0) or 0),
            "change": float(r.get("涨跌额", 0) or 0),
            "change_pct": float(r.get("涨跌幅", 0) or 0),
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "source": "AKShare/东方财富港股"
        }
    except Exception as e:
        logger.error(f"获取港股行情失败 {symbol}: {e}")
        return None


# ── 加密货币 ──────────────────────────────────────────────────────────

# 常见加密货币简写 → Binance 交易对 + 中文名
_CRYPTO_MAP = {
    "BTC":  ("BTCUSDT",  "比特币"),
    "ETH":  ("ETHUSDT",  "以太坊"),
    "BNB":  ("BNBUSDT",  "币安币"),
    "SOL":  ("SOLUSDT",  "Solana"),
    "XRP":  ("XRPUSDT",  "瑞波币"),
    "ADA":  ("ADAUSDT",  "艾达币"),
    "DOGE": ("DOGEUSDT", "狗狗币"),
    "USDT": ("USDCUSDT", "USDC"),
    "TON":  ("TONUSDT",  "Toncoin"),
    "AVAX": ("AVAXUSDT", "雪崩"),
    "LINK": ("LINKUSDT", "Chainlink"),
    "TRX":  ("TRXUSDT",  "波场"),
    "LTC":  ("LTCUSDT",  "莱特币"),
}


def get_crypto_quote(symbol: str) -> Optional[Dict]:
    """
    获取加密货币实时价格
    主接口：Binance REST API（无需账号，全球可访问）
    备接口：CoinGecko（via AKShare，速率有限制）
    symbol: 简写，如 'BTC', 'ETH'，或完整交易对如 'BTCUSDT'
    """
    s = symbol.upper().rstrip("USDT") if symbol.upper().endswith("USDT") else symbol.upper()
    
    entry = _CRYPTO_MAP.get(s)
    trading_pair = entry[0] if entry else s + "USDT"
    display_name = entry[1] if entry else s

    # ── 方案A：Binance 24h 行情 ──
    try:
        url = f"https://api.binance.com/api/v3/ticker/24hr?symbol={trading_pair}"
        resp = requests.get(url, timeout=5)
        data = resp.json()
        if "lastPrice" in data:
            price = float(data["lastPrice"])
            change_pct = float(data["priceChangePercent"])
            change = float(data["priceChange"])
            return {
                "symbol": s,
                "name": display_name,
                "asset_type": TYPE_CRYPTO,
                "price": price,
                "change": round(change, 4),
                "change_pct": change_pct,
                "open": float(data.get("openPrice", 0)),
                "high": float(data.get("highPrice", 0)),
                "low": float(data.get("lowPrice", 0)),
                "volume": float(data.get("volume", 0)),
                "turnover": float(data.get("quoteVolume", 0)),
                "market_cap": 0.0,
                "pe_ratio": 0.0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "Binance"
            }
    except Exception as e:
        logger.debug(f"Binance 接口失败 {symbol}: {e}")

    # ── 方案B：CoinGecko via AKShare ──
    ak = _lazy_akshare()
    if ak:
        coingecko_map = {
            "BTC": "bitcoin", "ETH": "ethereum", "BNB": "binancecoin",
            "SOL": "solana", "XRP": "ripple", "ADA": "cardano",
            "DOGE": "dogecoin",
        }
        cg_id = coingecko_map.get(s)
        if cg_id:
            try:
                df = ak.crypto_hist(symbol=cg_id, period="daily", start_date="today", end_date="today")
                if df is not None and not df.empty:
                    r = df.iloc[-1]
                    return {
                        "symbol": s,
                        "name": display_name,
                        "asset_type": TYPE_CRYPTO,
                        "price": float(r.get("收盘", 0) or 0),
                        "change": 0.0,
                        "change_pct": 0.0,
                        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "source": "CoinGecko"
                    }
            except Exception as e:
                logger.debug(f"CoinGecko 接口失败 {symbol}: {e}")

    logger.warning(f"未找到加密货币: {symbol}")
    return None


# ── 通用查询入口（自动识别资产类型） ─────────────────────────────────

# 美指 / 全球指数：用户可输入的别名 → 腾讯财经代码 + 中文名
_GLOBAL_INDEX_MAP = {
    # 美指
    "DJI":    ("us.DJI",   "道琼斯"),
    "DOW":    ("us.DJI",   "道琼斯"),
    "道琼斯": ("us.DJI",   "道琼斯"),
    "IXIC":   ("us.IXIC",  "纳斯达克"),
    "NASDAQ": ("us.IXIC",  "纳斯达克"),
    "纳斯达克":("us.IXIC", "纳斯达克"),
    "NDX":    ("us.IXIC",  "纳斯达克"),
    "INX":    ("us.INX",   "标普500"),
    "SPX":    ("us.INX",   "标普500"),
    "SP500":  ("us.INX",   "标普500"),
    "标普":   ("us.INX",   "标普500"),
    # 港股指数
    "HSI":    ("hkHSI",    "恒生指数"),
    "恒生":   ("hkHSI",    "恒生指数"),
}


def get_global_index_quote(alias: str) -> Optional[Dict]:
    """
    获取全球主要指数（美指/恒指等）
    主接口：腾讯财经 qt.gtimg.cn
    """
    entry = _GLOBAL_INDEX_MAP.get(alias.upper(), _GLOBAL_INDEX_MAP.get(alias))
    if not entry:
        return None
    tencent_code, display_name = entry
    try:
        resp = requests.get(_TENCENT_QUOTE_URL.format(symbols=tencent_code), timeout=5)
        resp.encoding = "gbk"
        for line in resp.text.splitlines():
            inner = line.split("~")
            if len(inner) < 33:
                continue
            price = float(inner[3]) if inner[3] else 0.0
            prev_close = float(inner[4]) if inner[4] else price
            change_amt = float(inner[31]) if len(inner) > 31 and inner[31] else round(price - prev_close, 2)
            change_pct = float(inner[32]) if len(inner) > 32 and inner[32] else 0.0
            return {
                "symbol": alias.upper(),
                "name": display_name,
                "asset_type": TYPE_INDEX,
                "price": price,
                "change": change_amt,
                "change_pct": change_pct,
                "open": float(inner[5]) if len(inner) > 5 and inner[5] else 0.0,
                "high": float(inner[33]) if len(inner) > 33 and inner[33] else 0.0,
                "low": float(inner[34]) if len(inner) > 34 and inner[34] else 0.0,
                "volume": 0.0,
                "turnover": 0.0,
                "market_cap": 0.0,
                "pe_ratio": 0.0,
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "source": "腾讯财经"
            }
    except Exception as e:
        logger.debug(f"全球指数查询失败 {alias}: {e}")
    return None


def get_us_stock_quote(symbol: str) -> Optional[Dict]:
    """
    获取美股实时行情
    主接口：腾讯财经（usAAPL 格式，无点号）
    备接口：AKShare stock_us_spot_em
    symbol: 美股代码，如 'AAPL', 'NVDA'
    """
    s = symbol.strip().upper()
    # ── 方案A：腾讯财经（格式 usNVDA，无点号） ──
    try:
        tencent_code = f"us{s}"
        resp = requests.get(_TENCENT_QUOTE_URL.format(symbols=tencent_code), timeout=5)
        resp.encoding = "gbk"
        for line in resp.text.splitlines():
            if s in line and "~" in line:
                inner = line.split("~")
                if len(inner) < 35:
                    continue
                name = inner[1].strip().replace(" ", "") or s
                price = float(inner[3]) if inner[3] else 0.0
                if price == 0:
                    continue
                change_amt = float(inner[31]) if len(inner) > 31 and inner[31] else 0.0
                change_pct = float(inner[32]) if len(inner) > 32 and inner[32] else 0.0
                high = float(inner[33]) if len(inner) > 33 and inner[33] else 0.0
                low = float(inner[34]) if len(inner) > 34 and inner[34] else 0.0
                return {
                    "symbol": s,
                    "name": name,
                    "asset_type": TYPE_US_STOCK,
                    "price": price,
                    "change": change_amt,
                    "change_pct": change_pct,
                    "open": float(inner[5]) if inner[5] else 0.0,
                    "high": high,
                    "low": low,
                    "volume": 0.0,
                    "turnover": 0.0,
                    "market_cap": 0.0,
                    "pe_ratio": 0.0,
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "腾讯财经"
                }
    except Exception as e:
        logger.debug(f"腾讯财经美股接口失败 {s}: {e}")

    # ── 方案B：AKShare 美股快照 ──
    ak = _lazy_akshare()
    if ak:
        try:
            df = ak.stock_us_spot_em()
            row = df[df["代码"].str.upper() == s]
            if row.empty:
                row = df[df["代码"].str.upper().str.endswith(f".{s}")]
            if not row.empty:
                r = row.iloc[0]
                return {
                    "symbol": s,
                    "name": str(r.get("名称", s)),
                    "asset_type": TYPE_US_STOCK,
                    "price": float(r.get("最新价", 0) or 0),
                    "change": float(r.get("涨跌额", 0) or 0),
                    "change_pct": float(r.get("涨跌幅", 0) or 0),
                    "open": float(r.get("今开", 0) or 0),
                    "high": float(r.get("最高", 0) or 0),
                    "low": float(r.get("最低", 0) or 0),
                    "volume": float(r.get("成交量", 0) or 0),
                    "turnover": float(r.get("成交额", 0) or 0),
                    "market_cap": float(r.get("总市值", 0) or 0),
                    "pe_ratio": float(r.get("市盈率-动态", 0) or 0),
                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "source": "AKShare/东方财富美股"
                }
        except Exception as e:
            logger.debug(f"AKShare 美股快照失败 {s}: {e}")

    logger.warning(f"未找到美股: {s}")
    return None


def auto_quote(symbol: str) -> Optional[Dict]:
    """
    自动识别资产类型并查询行情
    - 6位数字 → A股
    - 5位数字 → 港股
    - BTC/ETH等 → 加密货币
    - DJI/NASDAQ/SPX等 → 全球指数
    - 其他 → 尝试A股
    """
    s = symbol.strip().upper()

    # 港股：5位纯数字
    if s.isdigit() and len(s) == 5:
        return get_hk_stock_quote(s.zfill(5))

    # A股：6位纯数字
    if s.isdigit() and len(s) == 6:
        return get_stock_quote(s)

    # 加密货币：在 _CRYPTO_MAP 中或以 USDT 结尾
    if s in _CRYPTO_MAP or s.endswith("USDT"):
        return get_crypto_quote(s)

    # 全球指数：美指/恒指/日经等（含中文别名）
    if s in _GLOBAL_INDEX_MAP or symbol in _GLOBAL_INDEX_MAP:
        return get_global_index_quote(s if s in _GLOBAL_INDEX_MAP else symbol)

    # 美股：纯ASCII英文字母（1-5位，如 AAPL NVDA TSLA GOOG MSFT AMZN META）
    if s.isascii() and s.isalpha() and 1 <= len(s) <= 5:
        return get_us_stock_quote(s)

    # 默认尝试A股
    return get_stock_quote(s)


# ── 名称反查 ──────────────────────────────────────────────────────────

# A股代码前缀范围（上海：60/688/900，深圳：000/001/002/003/300/301）
_A_STOCK_PREFIXES = ("60", "688", "900", "000", "001", "002", "003", "300", "301")

def search_stock(keyword: str) -> List[Dict]:
    """
    根据名称或代码关键词搜索A股
    方案A：东方财富搜索 API（searchapi.eastmoney.com，非 push2，可访问）
    方案B：同花顺股票搜索（AKShare）
    方案C：pytdx 证券列表扫描（TCP，不依赖 HTTP CDN）
    方案D：AKShare 全市场快照扫描
    """
    # ── 方案A：东方财富搜索接口 ──
    _eastmoney_ok = False
    try:
        url = (
            "https://searchapi.eastmoney.com/api/suggest/get"
            f"?input={requests.utils.quote(keyword)}&type=14"
            "&token=D43BF722C8E33BDC906FB84D85E326E8&count=5"
        )
        resp = requests.get(url, timeout=5)
        data = resp.json()
        # 接口调用成功（不管有没有数据）
        _eastmoney_ok = resp.status_code == 200 and "QuotationCodeTable" in data
        items = data.get("QuotationCodeTable", {}).get("Data") or []
        results = []
        for item in items:
            code = str(item.get("Code", "") or "")
            name = str(item.get("Name", "") or "")
            sec_type = str(item.get("SecurityTypeName", "") or "")
            classify = str(item.get("Classify", "") or "")
            # A股：6位数字代码
            is_a_stock = code.isdigit() and len(code) == 6
            # 美股：字母代码（排除板块BK、基金衍生产品等，只保留普通股票 TypeUS=1）
            is_us_stock = classify == "UsStock" and code.isalpha() and len(code) <= 5 and item.get("TypeUS") == "1"
            if is_a_stock or is_us_stock:
                results.append({"symbol": code, "name": name})
        if results:
            return results[:5]
        # 方案A接口正常但0结果 → 该名称不存在，直接返回空，不再走慢速兜底
        if _eastmoney_ok:
            logger.debug(f"东方财富搜索 '{keyword}' 无结果，跳过兜底扫描")
            return []
    except Exception as e:
        logger.debug(f"东方财富搜索失败: {e}")

    # ── 方案B：同花顺股票搜索 ──
    ak = _lazy_akshare()
    if ak:
        try:
            df = ak.stock_search_detail_ths(symbol=keyword)
            if df is not None and not df.empty:
                results = []
                for _, r in df.head(5).iterrows():
                    code = str(r.get("代码", r.get("股票代码", "")) or "")
                    name = str(r.get("名称", r.get("股票名称", "")) or "")
                    if code and name:
                        results.append({"symbol": code, "name": name})
                if results:
                    return results
        except Exception as e:
            logger.debug(f"同花顺搜索失败: {e}")

    # ── 方案C：pytdx 证券列表扫描 ──
    api = _connect_tdx()
    if api:
        try:
            results = []
            kw = keyword.lower()
            for market in (0, 1):  # 0=深圳，1=上海
                start = 0
                while True:
                    batch = api.get_security_list(market, start)
                    if not batch:
                        break
                    for item in batch:
                        code = str(item.get("code", "") or "")
                        name_cn = str(item.get("name", "") or "")
                        if kw in name_cn.lower() or kw in code:
                            results.append({"symbol": code, "name": name_cn})
                            if len(results) >= 5:
                                break
                    if len(results) >= 5 or len(batch) < 1000:
                        break
                    start += 1000
                if len(results) >= 5:
                    break
            api.disconnect()
            if results:
                return results
        except Exception as e:
            logger.debug(f"pytdx 证券列表搜索失败: {e}")
            try:
                api.disconnect()
            except Exception:
                pass

    # ── 方案D：AKShare 全市场快照扫描 ──
    if ak:
        try:
            df = ak.stock_zh_a_spot_em()
            mask = df["名称"].str.contains(keyword, na=False)
            rows = df[mask].head(5)
            return [{"symbol": str(r["代码"]), "name": str(r["名称"])} for _, r in rows.iterrows()]
        except Exception as e:
            logger.debug(f"全市场搜索失败: {e}")

    return []
