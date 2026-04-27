#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人一键配置工具

使用飞书官方 Device Code Flow 扫码自动创建应用，
并将 app_id、app_secret、open_id 写入 config.py。

用法:
    python feishu_setup.py
"""

from typing import Optional
import json
import time
import sys
import re
from urllib.request import urlopen, Request
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

ACCOUNTS_URL = "https://accounts.feishu.cn"
REGISTRATION_PATH = "/oauth/v1/app/registration"
REQUEST_TIMEOUT = 10


def _post(body: dict) -> dict:
    url = f"{ACCOUNTS_URL}{REGISTRATION_PATH}"
    data = urlencode(body).encode("utf-8")
    req = Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        with urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except HTTPError as exc:
        body_bytes = exc.read()
        if body_bytes:
            try:
                return json.loads(body_bytes.decode("utf-8"))
            except (ValueError, json.JSONDecodeError):
                pass
        raise


def _render_qr_terminal(url: str) -> bool:
    """在终端渲染二维码，返回是否成功"""
    try:
        import qrcode
        qr = qrcode.QRCode(border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qr.print_ascii(invert=True)
        return True
    except Exception:
        return False


def _init():
    res = _post({"action": "init"})
    methods = res.get("supported_auth_methods") or []
    if "client_secret" not in methods:
        raise RuntimeError(f"当前环境不支持 client_secret 认证，支持的方式: {methods}")


def _begin() -> dict:
    res = _post({
        "action": "begin",
        "archetype": "PersonalAgent",
        "auth_method": "client_secret",
        "request_user_info": "open_id",
    })
    device_code = res.get("device_code")
    if not device_code:
        raise RuntimeError("飞书未返回 device_code，请检查网络连接")
    qr_url = res.get("verification_uri_complete", "")
    return {
        "device_code": device_code,
        "qr_url": qr_url,
        "interval": res.get("interval") or 5,
        "expire_in": res.get("expire_in") or 600,
    }


def _poll(device_code: str, interval: int, expire_in: int) -> Optional[dict]:
    deadline = time.time() + expire_in
    count = 0
    while time.time() < deadline:
        try:
            res = _post({"action": "poll", "device_code": device_code, "tp": "ob_app"})
        except (URLError, OSError, json.JSONDecodeError):
            time.sleep(interval)
            continue

        count += 1
        if count == 1:
            print("  等待扫码确认", end="", flush=True)
        elif count % 3 == 0:
            print(".", end="", flush=True)

        if res.get("client_id") and res.get("client_secret"):
            print()
            user_info = res.get("user_info") or {}
            return {
                "app_id": res["client_id"],
                "app_secret": res["client_secret"],
                "open_id": user_info.get("open_id"),
            }

        error = res.get("error", "")
        if error in ("access_denied", "expired_token"):
            print()
            print(f"❌ 扫码被拒绝或已超时: {error}")
            return None

        time.sleep(interval)

    print()
    print("❌ 等待超时，请重新运行")
    return None


def _write_config(app_id: str, app_secret: str, open_id: str):
    """将飞书凭证写入 config.py"""
    try:
        with open("config.py", "r", encoding="utf-8") as f:
            content = f.read()
    except FileNotFoundError:
        print("❌ 找不到 config.py，请先运行: cp config.example.py config.py")
        sys.exit(1)

    def replace_or_append(text, key, value):
        pattern = rf'^{key}\s*=.*$'
        replacement = f'{key} = "{value}"'
        new_text, n = re.subn(pattern, replacement, text, flags=re.MULTILINE)
        if n == 0:
            new_text = text.rstrip() + f'\n{replacement}\n'
        return new_text

    content = replace_or_append(content, "FEISHU_APP_ID", app_id)
    content = replace_or_append(content, "FEISHU_APP_SECRET", app_secret)
    if open_id:
        content = replace_or_append(content, "FEISHU_OPEN_ID", open_id)

    with open("config.py", "w", encoding="utf-8") as f:
        f.write(content)


def main():
    print("=" * 50)
    print("🚀 飞书机器人一键配置")
    print("=" * 50)
    print()

    print("  正在连接飞书...", end="", flush=True)
    try:
        _init()
        begin = _begin()
    except Exception as e:
        print(f"\n❌ 连接失败: {e}")
        sys.exit(1)
    print(" 完成")
    print()

    qr_url = begin["qr_url"]
    rendered = _render_qr_terminal(qr_url)
    if rendered:
        print(f"\n  👆 用飞书 App 扫描上方二维码")
    else:
        print(f"  📱 用飞书 App 打开以下链接（或复制到手机浏览器）：")
        print(f"\n  {qr_url}\n")
        print("  💡 提示：安装 qrcode 可直接在终端显示二维码：pip install qrcode[pil]")

    print()
    result = _poll(begin["device_code"], begin["interval"], begin["expire_in"])
    if not result:
        sys.exit(1)

    app_id = result["app_id"]
    app_secret = result["app_secret"]
    open_id = result.get("open_id")

    print()
    print("✅ 扫码成功！")
    print(f"   App ID:     {app_id}")
    print(f"   App Secret: {app_secret[:6]}{'*' * (len(app_secret) - 6)}")
    if open_id:
        print(f"   你的 open_id: {open_id}")
    print()

    _write_config(app_id, app_secret, open_id)
    print("✅ 配置已写入 config.py")
    print()

    if not open_id:
        print("⚠️  未获取到你的 open_id，私聊推送需要手动设置 FEISHU_OPEN_ID")
        print("   可以在飞书群里把机器人加进去，然后用 python feishu_bot.py 获取")
    else:
        print("🎉 配置完成！现在可以运行价格监控了：")
        print("   python price_monitor.py --test   # 测试")
        print("   python price_monitor.py          # 启动监控")

    print()
    print("=" * 50)


if __name__ == "__main__":
    main()
