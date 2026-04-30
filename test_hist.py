import akshare as ak
from datetime import datetime
today = datetime.now().strftime('%Y%m%d')
df = ak.stock_zh_a_hist(symbol='600519', period='daily', start_date=today, end_date=today, adjust='')
print(df.columns.tolist())
print(df.iloc[0].to_dict())
