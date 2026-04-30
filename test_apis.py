import akshare as ak

# 测试哪些接口可用
tests = [
    ('stock_individual_info_em', lambda: ak.stock_individual_info_em(symbol='600519')),
    ('stock_zh_a_hist_min_em', lambda: ak.stock_zh_a_hist_min_em(symbol='600519', start_date='2026-04-28 09:30:00', end_date='2026-04-28 15:30:00', period='1')),
    ('stock_intraday_em', lambda: ak.stock_intraday_em(symbol='600519')),
]
for name, fn in tests:
    try:
        result = fn()
        print(f"OK: {name} -> {type(result)} len={len(result)}")
        print(result.head(2))
    except Exception as e:
        print(f"FAIL: {name} -> {e.__class__.__name__}: {str(e)[:80]}")
    print()
