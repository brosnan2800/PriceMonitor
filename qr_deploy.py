#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
飞书机器人二维码部署工具
帮助用户通过二维码快速部署飞书机器人
"""

import qrcode
import qrcode.image.svg
import os
import sys
import json
from typing import Optional
import argparse


def generate_qr_code(data: str, output_file: str = None,
                    format: str = "png") -> Optional[str]:
    """
    生成二维码图片

    Args:
        data: 要编码的数据（通常是URL）
        output_file: 输出文件路径，如果不提供则生成临时文件
        format: 输出格式，支持 png, svg

    Returns:
        str: 生成的二维码文件路径，失败返回 None
    """
    try:
        # 创建二维码实例
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(data)
        qr.make(fit=True)

        # 生成二维码图片
        if format.lower() == "svg":
            if not output_file:
                output_file = "feishu_bot_qr.svg"
            img = qr.make_image(image_factory=qrcode.image.svg.SvgImage)
        else:
            if not output_file:
                output_file = "feishu_bot_qr.png"
            img = qr.make_image(fill_color="black", back_color="white")

        # 保存图片
        img.save(output_file)
        print(f"✅ 二维码已生成: {output_file}")
        print(f"🔗 编码数据: {data}")

        return output_file

    except Exception as e:
        print(f"❌ 生成二维码失败: {e}")
        return None


def generate_feishu_bot_url(app_id: str) -> str:
    """
    生成飞书机器人添加链接

    Args:
        app_id: 飞书开放平台应用 ID

    Returns:
        str: 飞书机器人添加链接
    """
    # 飞书机器人添加链接格式
    return f"https://applink.feishu.cn/client/bot/open?appId={app_id}"


def display_deployment_guide(app_id: str, app_secret: str, qr_file: str = None):
    """
    显示部署指南

    Args:
        app_id: 飞书应用 ID
        app_secret: 飞书应用密钥
        qr_file: 二维码文件路径（可选）
    """
    print("\n" + "="*60)
    print("🚀 飞书机器人部署指南")
    print("="*60)

    print("\n📋 第一步：配置应用")
    print(f"   应用 ID (FEISHU_APP_ID): {app_id}")
    print(f"   应用密钥 (FEISHU_APP_SECRET): {app_secret}")
    print("   请将这些信息添加到 config.py 文件中：")
    print("   ---")
    print("   FEISHU_APP_ID = \"" + app_id + "\"")
    print("   FEISHU_APP_SECRET = \"" + app_secret + "\"")
    print("   FEISHU_CHAT_ID = \"\"  # 暂留空，稍后获取")
    print("   ---")

    print("\n📱 第二步：添加机器人到飞书")
    print("   1. 打开飞书 App")
    print("   2. 扫描下面的二维码")

    if qr_file:
        print(f"   3. 或者手动点击链接: {generate_feishu_bot_url(app_id)}")
        print(f"\n💡 二维码文件: {qr_file}")
    else:
        print(f"   链接: {generate_feishu_bot_url(app_id)}")

    print("\n👥 第三步：获取 Chat ID")
    print("   方法 A: 通过 API 获取（推荐）")
    print("     1. 运行: python feishu_bot.py")
    print("     2. 程序会列出机器人所在的群聊")
    print("     3. 复制 chat_id 到配置中")
    print()
    print("   方法 B: 手动获取")
    print("     1. 在飞书群聊中 @机器人")
    print("     2. 查看群聊设置中的群聊 ID")
    print("     3. 或者在浏览器地址栏查看群聊链接中的 ID")

    print("\n⚙️ 第四步：完成配置")
    print("   1. 将获取的 chat_id 填入 FEISHU_CHAT_ID")
    print("   2. 重启价格监控系统")
    print("   3. 运行测试: python feishu_bot.py")

    print("\n" + "="*60)
    print("🎉 部署完成！机器人现在可以发送价格通知了。")
    print("="*60)


def get_chat_id_guide():
    """获取 Chat ID 的详细指南"""
    print("\n" + "="*60)
    print("🔍 如何获取飞书 Chat ID")
    print("="*60)

    print("\n方法一：通过 API 自动获取（推荐）")
    print("   1. 确保已经配置了 FEISHU_APP_ID 和 FEISHU_APP_SECRET")
    print("   2. 运行: python feishu_bot.py")
    print("   3. 如果机器人已添加到群聊，程序会列出所有群聊")
    print("   4. 从列表中选择一个 chat_id")

    print("\n方法二：手动从飞书获取")
    print("   1. 在桌面版飞书中打开群聊")
    print("   2. 点击右上角的群聊设置图标")
    print("   3. 找到「群聊 ID」或「群号」")
    print("   4. 复制该 ID")

    print("\n方法三：从群聊链接获取")
    print("   1. 在浏览器中打开飞书网页版")
    print("   2. 进入目标群聊")
    print("   3. 查看浏览器地址栏，URL 格式类似：")
    print("      https://applink.feishu.cn/client/chat/{chat_id}/...")
    print("   4. 复制 {chat_id} 部分")

    print("\n💡 注意事项：")
    print("   • Chat ID 可能是数字或字符串")
    print("   • 确保机器人有该群聊的发送消息权限")
    print("   • 如果需要发送给个人，需要使用用户的 open_id")

    print("\n" + "="*60)


def main():
    """主函数"""
    parser = argparse.ArgumentParser(description="飞书机器人二维码部署工具")
    parser.add_argument("--app-id", help="飞书应用 ID")
    parser.add_argument("--app-secret", help="飞书应用密钥")
    parser.add_argument("--output", "-o", default="feishu_bot_qr.png",
                       help="二维码输出文件路径 (默认: feishu_bot_qr.png)")
    parser.add_argument("--format", default="png", choices=["png", "svg"],
                       help="二维码格式 (默认: png)")
    parser.add_argument("--guide", action="store_true",
                       help="显示 Chat ID 获取指南")
    parser.add_argument("--config", action="store_true",
                       help="从 config.py 读取配置")

    args = parser.parse_args()

    # 如果请求指南，显示并退出
    if args.guide:
        get_chat_id_guide()
        return

    # 尝试从配置文件读取
    app_id = args.app_id
    app_secret = args.app_secret

    if args.config:
        try:
            import config
            if hasattr(config, 'FEISHU_APP_ID'):
                app_id = config.FEISHU_APP_ID
            if hasattr(config, 'FEISHU_APP_SECRET'):
                app_secret = config.FEISHU_APP_SECRET
        except ImportError:
            print("⚠️  无法导入 config.py，请使用 --app-id 和 --app-secret 参数")
        except Exception as e:
            print(f"⚠️  读取配置失败: {e}")

    # 检查必要的参数
    if not app_id or not app_secret:
        print("❌ 请提供飞书应用 ID 和密钥")
        print()
        parser.print_help()
        print()
        print("示例:")
        print("  python qr_deploy.py --app-id cli_xxxx --app-secret xxxxxxxx")
        print("  python qr_deploy.py --config  # 从 config.py 读取配置")
        return

    # 生成飞书机器人添加链接
    bot_url = generate_feishu_bot_url(app_id)

    # 生成二维码
    qr_file = generate_qr_code(bot_url, args.output, args.format)

    # 显示部署指南
    display_deployment_guide(app_id, app_secret, qr_file)

    print("\n📝 快速命令:")
    print(f"   测试连接: python feishu_bot.py")
    print(f"   查看二维码: open {qr_file if qr_file else 'feishu_bot_qr.png'}")
    print(f"   再次生成: python qr_deploy.py --app-id {app_id} --app-secret {app_secret}")


if __name__ == "__main__":
    main()