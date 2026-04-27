#!/bin/bash

# USD/CNH 和 布伦特原油价格监控系统测试脚本
# 用法: ./test_all.sh

echo "=============================="
echo "价格监控系统测试脚本"
echo "=============================="

# 检查Python版本
echo "检查Python版本..."
python3 --version

if [ $? -ne 0 ]; then
    echo "错误: Python 3未安装"
    exit 1
fi

# 检查依赖
echo "检查依赖包..."
python3 -c "import requests" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "安装依赖包..."
    pip install -r requirements.txt
fi

# 检查配置文件
echo "检查配置文件..."
if [ -f "config.py" ]; then
    echo "✓ 找到 config.py"
else
    if [ -f "config.example.py" ]; then
        echo "⚠️  请复制 config.example.py 为 config.py 并填写设置"
        cp config.example.py config.py
        echo "已创建 config.py，请编辑文件填写您的设置"
        exit 1
    else
        echo "❌ 找不到配置文件"
        exit 1
    fi
fi

# 测试数据收集模块
echo "测试数据收集模块..."
python3 -c "
import sys
sys.path.append('.')
try:
    from data_collector import AlphaVantageCollector
    import config
    collector = AlphaVantageCollector(config.ALPHA_VANTAGE_API_KEY)
    print('✓ 数据收集模块导入成功')
except Exception as e:
    print(f'❌ 数据收集模块导入失败: {e}')
"

# 测试Telegram模块
echo "测试Telegram模块..."
python3 -c "
import sys
sys.path.append('.')
try:
    from telegram_bot import TelegramBot
    import config
    bot = TelegramBot(config.TELEGRAM_BOT_TOKEN, config.TELEGRAM_CHAT_ID)
    print('✓ Telegram模块导入成功')
except Exception as e:
    print(f'❌ Telegram模块导入失败: {e}')
"

# 测试主要模块
echo "测试主监控模块..."
python3 -c "
import sys
sys.path.append('.')
try:
    from price_monitor import PriceMonitor
    print('✓ 主监控模块导入成功')
except Exception as e:
    print(f'❌ 主监控模块导入失败: {e}')
"

# 运行单元测试
echo "运行单元测试..."
python3 -c "
import sys
sys.path.append('.')

# 测试配置
try:
    import config
    print(f'AlphaVantage密钥: {config.ALPHA_VANTAGE_API_KEY[:10]}...')
    print(f'Telegram Token: {config.TELEGRAM_BOT_TOKEN[:10]}...')
    print(f'监控间隔: {getattr(config, 'MONITOR_INTERVAL_MINUTES', 5)}分钟')
    print('✓ 配置读取成功')
except Exception as e:
    print(f'⚠️  配置读取警告: {e}')
"

echo ""
echo "=============================="
echo "准备完成!"
echo "以下是下一步操作:"
echo "=============================="
echo ""
echo "1. 确保已正确填写 config.py 文件"
echo "2. 测试系统连接: python price_monitor.py --test"
echo "3. 单次运行测试: python price_monitor.py --once"
echo "4. 启动监控: python price_monitor.py"
echo "5. 交互模式: python price_monitor.py --interactive"
echo ""
echo "详细文档请查看 setup_guide.md"
echo "=============================="