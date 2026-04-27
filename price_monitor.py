#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
价格监控主程序
监控USD/CNH汇率和布伦特原油价格，通过Telegram推送
"""

import time
import schedule
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import signal
import sys
import os

# 导入自定义模块
from data_collector import AlphaVantageCollector
from telegram_bot import TelegramBot
from feishu_bot import FeishuBot

# 尝试导入配置
try:
    import config
    CONFIG_LOADED = True
except ImportError:
    CONFIG_LOADED = False


class PriceMonitor:
    """价格监控主类"""

    def __init__(self):
        """初始化监控器"""
        self.setup_logging()
        self.load_config()
        self.setup_services()
        self.running = True

        # 信号处理
        signal.signal(signal.SIGINT, self.signal_handler)
        signal.signal(signal.SIGTERM, self.signal_handler)

        logger.info("价格监控系统初始化完成")

    def setup_logging(self):
        """设置日志"""
        self.logger = logging.getLogger(__name__)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)

        # 文件处理器
        file_handler = logging.FileHandler('price_monitor.log')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)

        # 设置根日志器
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.DEBUG)
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

        global logger
        logger = self.logger

    def load_config(self):
        """加载配置"""
        if CONFIG_LOADED:
            self.config = config
            logger.info("从config.py加载配置")
        else:
            # 尝试从环境变量加载配置
            self.load_config_from_env()
            logger.info("从环境变量加载配置")

        # 设置监控间隔
        self.check_interval = getattr(self.config, 'MONITOR_INTERVAL_MINUTES', 5)

        # 价格阈值设置
        self.thresholds = {
            "usd_cnh_upper": getattr(self.config, 'USD_CNH_UPPER_THRESHOLD', 7.15),
            "usd_cnh_lower": getattr(self.config, 'USD_CNH_LOWER_THRESHOLD', 7.10),
            "oil_change_percent": getattr(self.config, 'BRENT_OIL_CHANGE_THRESHOLD_PERCENT', 1.0)
        }

    def load_config_from_env(self):
        """从环境变量加载配置"""
        import os
        from dotenv import load_dotenv

        load_dotenv()

        # 创建简单的配置对象
        class Config:
            pass

        self.config = Config()

        # Alpha Vantage配置
        self.config.ALPHA_VANTAGE_API_KEY = os.getenv(
            "ALPHA_VANTAGE_API_KEY",
            "YOUR_API_KEY"
        )

        # Telegram配置
        self.config.TELEGRAM_BOT_TOKEN = os.getenv(
            "TELEGRAM_BOT_TOKEN",
            "YOUR_BOT_TOKEN"
        )
        self.config.TELEGRAM_CHAT_ID = os.getenv(
            "TELEGRAM_CHAT_ID",
            "YOUR_CHAT_ID"
        )

        # 监控配置
        self.config.MONITOR_INTERVAL_MINUTES = int(os.getenv(
            "MONITOR_INTERVAL_MINUTES",
            "5"
        ))

        # 阈值配置
        self.config.USD_CNH_UPPER_THRESHOLD = float(os.getenv(
            "USD_CNH_UPPER_THRESHOLD",
            "7.15"
        ))
        self.config.USD_CNH_LOWER_THRESHOLD = float(os.getenv(
            "USD_CNH_LOWER_THRESHOLD",
            "7.10"
        ))
        self.config.BRENT_OIL_CHANGE_THRESHOLD_PERCENT = float(os.getenv(
            "BRENT_OIL_CHANGE_THRESHOLD_PERCENT",
            "1.0"
        ))

        # 飞书配置（可选）
        self.config.FEISHU_APP_ID = os.getenv(
            "FEISHU_APP_ID",
            ""
        )
        self.config.FEISHU_APP_SECRET = os.getenv(
            "FEISHU_APP_SECRET",
            ""
        )
        self.config.FEISHU_CHAT_ID = os.getenv(
            "FEISHU_CHAT_ID",
            ""
        )

        # 平台选择配置
        self.config.ENABLED_PLATFORMS = os.getenv(
            "ENABLED_PLATFORMS",
            "telegram,feishu"
        ).split(",") if os.getenv("ENABLED_PLATFORMS") else ["telegram", "feishu"]

        self.config.NOTIFICATION_PLATFORM = os.getenv(
            "NOTIFICATION_PLATFORM",
            "all"
        )

    def setup_services(self):
        """设置数据收集和推送服务"""
        # 初始化数据收集器
        self.collector = AlphaVantageCollector(
            api_key=self.config.ALPHA_VANTAGE_API_KEY,
            request_interval=getattr(self.config, 'API_REQUEST_INTERVAL_SECONDS', 2)
        )

        # 初始化消息推送机器人
        self.bots = []  # 存储所有机器人实例

        # 检查启用的平台
        enabled_platforms = getattr(self.config, 'ENABLED_PLATFORMS', ["telegram", "feishu"])
        notification_platform = getattr(self.config, 'NOTIFICATION_PLATFORM', 'all')

        # Telegram机器人
        if 'telegram' in enabled_platforms and notification_platform in ['telegram', 'all']:
            if (hasattr(self.config, 'TELEGRAM_BOT_TOKEN') and
                hasattr(self.config, 'TELEGRAM_CHAT_ID') and
                self.config.TELEGRAM_BOT_TOKEN and
                self.config.TELEGRAM_BOT_TOKEN != "YOUR_BOT_TOKEN"):
                try:
                    self.telegram_bot = TelegramBot(
                        bot_token=self.config.TELEGRAM_BOT_TOKEN,
                        chat_id=self.config.TELEGRAM_CHAT_ID
                    )
                    self.bots.append(("telegram", self.telegram_bot))
                    logger.info("Telegram机器人已初始化")
                except Exception as e:
                    logger.error(f"初始化Telegram机器人失败: {e}")
                    self.telegram_bot = None
            else:
                logger.warning("Telegram配置不完整，跳过初始化")
                self.telegram_bot = None
        else:
            self.telegram_bot = None

        # 飞书机器人
        if 'feishu' in enabled_platforms and notification_platform in ['feishu', 'all']:
            if (hasattr(self.config, 'FEISHU_APP_ID') and
                hasattr(self.config, 'FEISHU_APP_SECRET') and
                self.config.FEISHU_APP_ID and
                self.config.FEISHU_APP_SECRET):
                try:
                    self.feishu_bot = FeishuBot(
                        app_id=self.config.FEISHU_APP_ID,
                        app_secret=self.config.FEISHU_APP_SECRET,
                        chat_id=getattr(self.config, 'FEISHU_CHAT_ID', ''),
                        open_id=getattr(self.config, 'FEISHU_OPEN_ID', '')
                    )
                    self.bots.append(("feishu", self.feishu_bot))
                    logger.info("飞书机器人已初始化")
                except Exception as e:
                    logger.error(f"初始化飞书机器人失败: {e}")
                    self.feishu_bot = None
            else:
                logger.warning("飞书配置不完整，跳过初始化")
                self.feishu_bot = None
        else:
            self.feishu_bot = None

        # 如果没有启用任何机器人
        if not self.bots:
            logger.error("未配置任何消息推送平台，系统无法发送通知")
            logger.error("请至少配置 Telegram 或飞书机器人")
            sys.exit(1)

        # 测试服务连接
        if not self.test_services():
            logger.error("服务连接测试失败，系统将退出")
            sys.exit(1)

    def test_services(self) -> bool:
        """测试所有服务连接"""
        try:
            logger.info("测试服务连接...")

            success_count = 0
            start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            start_message = (
                f"🚀 *价格监控系统启动*\n\n"
                f"• 启动时间: {start_time}\n"
                f"• 监控间隔: {self.check_interval}分钟\n"
                f"• 监控资产:\n"
                f"  - USD/CNH汇率\n"
                f"  - 布伦特原油价格"
            )

            # 测试所有机器人连接并发送启动消息
            for platform, bot in self.bots:
                try:
                    if platform == "telegram":
                        # Telegram使用Markdown格式
                        if not bot.test_connection():
                            logger.error(f"Telegram连接失败")
                            continue
                        bot.send_message(start_message)
                    elif platform == "feishu":
                        # 飞书连接测试（简化）
                        if not bot.test_connection():
                            logger.error(f"飞书连接失败")
                            continue
                        # 飞书可能不支持Markdown，发送纯文本版本
                        text_message = start_message.replace("*", "")
                        bot.send_message(text_message)

                    success_count += 1
                    logger.info(f"{platform} 连接测试成功")

                except Exception as e:
                    logger.error(f"{platform} 连接测试异常: {e}")

            # 如果至少一个平台成功，则整个系统成功
            if success_count > 0:
                logger.info(f"服务连接测试成功 ({success_count}/{len(self.bots)} 个平台)")
                return True
            else:
                logger.error("所有消息平台连接失败")
                return False

        except Exception as e:
            logger.error(f"服务连接测试异常: {e}")
            return False

    def run_once(self, send_report: bool = True) -> bool:
        """
        执行一次完整的价格检查

        Args:
            send_report: 是否发送报告

        Returns:
            bool: 是否成功
        """
        try:
            logger.info("开始执行价格检查...")

            # 获取所有价格数据
            price_data = self.collector.get_all_prices()

            if not price_data:
                logger.error("获取价格数据失败")
                return False

            # 检查提醒阈值
            alerts = []
            for asset_name, data in price_data.items():
                asset_alerts = self.collector.check_price_alerts(data, self.thresholds)
                alerts.extend(asset_alerts)

            # 计算下次检查时间
            next_check_time = (datetime.now() + timedelta(minutes=self.check_interval)).strftime("%H:%M:%S")

            # 发送报告到所有平台
            if send_report:
                success_count = 0
                for platform, bot in self.bots:
                    try:
                        if platform == "telegram":
                            success = bot.send_price_report(
                                price_data=price_data,
                                alerts=alerts if alerts else None,
                                next_check_time=next_check_time
                            )
                        elif platform == "feishu":
                            # 飞书机器人使用相同的方法签名
                            success = bot.send_price_report(
                                price_data=price_data,
                                alerts=alerts if alerts else None,
                                next_check_time=next_check_time
                            )
                        else:
                            success = False

                        if success:
                            success_count += 1
                            logger.info(f"{platform} 价格报告发送成功")
                        else:
                            logger.error(f"{platform} 价格报告发送失败")
                    except Exception as e:
                        logger.error(f"{platform} 发送价格报告异常: {e}")

                if success_count > 0:
                    logger.info(f"价格报告发送成功 ({success_count}/{len(self.bots)} 个平台)")
                else:
                    logger.error("所有平台价格报告发送失败")

            # 如果有提醒，发送额外提醒消息到所有平台
            if alerts:
                for alert in alerts:
                    for platform, bot in self.bots:
                        try:
                            if platform == "telegram":
                                bot.send_alert(alert)
                            elif platform == "feishu":
                                bot.send_alert(alert)
                        except Exception as e:
                            logger.error(f"{platform} 发送提醒异常: {e}")

            # 记录价格数据
            self.log_prices(price_data)

            return True

        except Exception as e:
            logger.error(f"价格检查异常: {e}")
            return False

    def log_prices(self, price_data: Dict):
        """记录价格数据到文件"""
        try:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            log_entry = {
                "timestamp": timestamp,
                "prices": price_data
            }

            # 记录到JSON文件
            import json
            log_file = "price_history.json"

            # 读取现有数据或创建新文件
            if os.path.exists(log_file):
                with open(log_file, 'r', encoding='utf-8') as f:
                    try:
                        history = json.load(f)
                        if not isinstance(history, list):
                            history = []
                    except json.JSONDecodeError:
                        history = []
            else:
                history = []

            # 添加新记录
            history.append(log_entry)

            # 只保留最近1000条记录
            if len(history) > 1000:
                history = history[-1000:]

            # 写回文件
            with open(log_file, 'w', encoding='utf-8') as f:
                json.dump(history, f, ensure_ascii=False, indent=2)

            logger.debug(f"价格数据已保存到 {log_file}")

        except Exception as e:
            logger.error(f"保存价格数据失败: {e}")

    def signal_handler(self, signum, frame):
        """信号处理函数"""
        logger.info(f"收到信号 {signum}，正在关闭...")
        self.running = False

        # 发送关闭消息到所有平台
        shutdown_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        shutdown_message = (
            f"🛑 *价格监控系统关闭*\n\n"
            f"• 关闭时间: {shutdown_time}\n"
            f"• 系统已运行: {self.get_uptime()}"
        )

        for platform, bot in self.bots:
            try:
                if platform == "telegram":
                    bot.send_message(shutdown_message)
                elif platform == "feishu":
                    # 飞书可能不支持Markdown
                    text_message = shutdown_message.replace("*", "")
                    bot.send_message(text_message)
            except Exception as e:
                logger.error(f"{platform} 发送关闭消息异常: {e}")

        sys.exit(0)

    def get_uptime(self) -> str:
        """获取系统运行时间"""
        if hasattr(self, 'start_time'):
            uptime = datetime.now() - self.start_time
            days = uptime.days
            hours, remainder = divmod(uptime.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)

            if days > 0:
                return f"{days}天 {hours}小时 {minutes}分钟"
            elif hours > 0:
                return f"{hours}小时 {minutes}分钟"
            else:
                return f"{minutes}分钟"
        return "未知"

    def run_scheduled(self):
        """运行计划任务"""
        logger.info(f"启动计划任务，每{self.check_interval}分钟检查一次")

        # 记录启动时间
        self.start_time = datetime.now()

        # 立即执行一次检查
        logger.info("执行首次检查...")
        self.run_once()

        # 设置定时任务
        schedule.every(self.check_interval).minutes.do(self.run_once)

        # 每天凌晨发送汇总报告
        schedule.every().day.at("00:00").do(self.send_daily_summary)

        # 主循环
        while self.running:
            try:
                schedule.run_pending()
                time.sleep(1)
            except KeyboardInterrupt:
                logger.info("收到键盘中断")
                self.running = False
            except Exception as e:
                logger.error(f"计划任务异常: {e}")
                time.sleep(60)  # 异常后等待1分钟再继续

    def send_daily_summary(self):
        """发送每日汇总报告"""
        try:
            # 读取当天数据
            import json
            from datetime import datetime

            log_file = "price_history.json"
            if not os.path.exists(log_file):
                return

            with open(log_file, 'r', encoding='utf-8') as f:
                try:
                    history = json.load(f)
                except json.JSONDecodeError:
                    return

            # 筛选当天数据
            today = datetime.now().strftime("%Y-%m-%d")
            daily_data = [
                entry["prices"]
                for entry in history
                if entry["timestamp"].startswith(today)
            ]

            if daily_data:
                # 发送汇总报告到所有支持的平台
                for platform, bot in self.bots:
                    try:
                        if platform == "telegram":
                            bot.send_daily_summary(daily_data)
                            logger.info("Telegram每日汇总发送成功")
                        # 飞书暂不支持每日汇总功能
                    except Exception as e:
                        logger.error(f"{platform} 发送每日汇总异常: {e}")

        except Exception as e:
            logger.error(f"发送每日汇总失败: {e}")

    def interactive_mode(self):
        """交互式模式"""
        print(f"\n=== 价格监控系统交互模式 ===")
        print(f"监控间隔: {self.check_interval}分钟")
        print(f"监控资产: USD/CNH汇率, 布伦特原油")
        print("=" * 40)
        print("命令:")
        print("  c - 立即检查价格")
        print("  s - 启动定时监控")
        print("  t - 测试服务连接")
        print("  q - 退出")
        print("=" * 40)

        while True:
            try:
                command = input("\n输入命令: ").strip().lower()

                if command == 'c':
                    print("正在检查价格...")
                    if self.run_once():
                        print("✓ 检查完成")
                    else:
                        print("✗ 检查失败")

                elif command == 's':
                    print(f"启动每{self.check_interval}分钟定时监控...")
                    print("按 Ctrl+C 停止")
                    self.run_scheduled()

                elif command == 't':
                    print("测试服务连接...")
                    if self.test_services():
                        print("✓ 所有服务连接正常")
                    else:
                        print("✗ 服务连接测试失败")

                elif command == 'q':
                    print("正在退出...")
                    break

                else:
                    print("未知命令，请输入 c, s, t 或 q")

            except KeyboardInterrupt:
                print("\n收到中断信号")
                break
            except Exception as e:
                print(f"错误: {e}")


def main():
    """主函数"""
    print("=" * 50)
    print("      USD/CNH 和 布伦特原油价格监控系统")
    print("=" * 50)

    # 初始化监控器
    monitor = PriceMonitor()

    # 检查参数
    if len(sys.argv) > 1:
        if sys.argv[1] == "--once":
            # 单次运行模式
            print("单次运行模式...")
            monitor.run_once()
        elif sys.argv[1] == "--test":
            # 测试模式
            print("测试模式...")
            monitor.test_services()
        elif sys.argv[1] == "--interactive":
            # 交互模式
            monitor.interactive_mode()
        else:
            print(f"未知参数: {sys.argv[1]}")
            print("可用参数:")
            print("  --once         单次运行")
            print("  --test         测试服务")
            print("  --interactive  交互模式")
            print("  无参数         启动定时监控")
    else:
        # 默认启动定时监控
        print(f"启动定时监控，每{monitor.check_interval}分钟检查一次...")
        print("按 Ctrl+C 停止")
        monitor.run_scheduled()


if __name__ == "__main__":
    main()