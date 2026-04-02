from ibapi.client import EClient
from ibapi.wrapper import EWrapper
import time

class TestApp(EWrapper, EClient):
    def __init__(self):
        EClient.__init__(self, self)
    
    def error(self, reqId, code, msg):
        print(f"Error {code}: {msg}")
    
    def nextValidId(self, orderId):
        print(f"✅ 连接成功，下一个有效订单ID: {orderId}")
        self.disconnect()

app = TestApp()
app.connect('172.29.80.1', 7497, clientId=1)
time.sleep(3)
app.run()