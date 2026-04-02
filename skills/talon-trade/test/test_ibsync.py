from ib_insync import IB
ib = IB()
ib.connect('172.29.80.1', 7497, clientId=1, timeout=30)  # 延长超时到30秒
print('✅ 连接成功')
ib.disconnect()