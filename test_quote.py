from data.sources.akshare_source import auto_quote, search_stock
r = auto_quote('600519')
if r:
    print("成功:", r['name'], r['price'], r['change_pct'])
else:
    print("失败: 返回None")

results = search_stock('贵州茅台')
print("搜索结果:", results)
