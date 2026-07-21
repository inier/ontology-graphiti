import requests
import json

url = "http://localhost:8000/api/he/extract"
data = {
    "text": "我们的系统管理客户和订单。每个客户可以下多个订单，每个订单包含多个商品。客户有姓名、电话和地址。订单有订单号、日期和金额。",
    "ontology_id": "test"
}

response = requests.post(url, json=data)
print(f"Status: {response.status_code}")
print(f"Response: {response.text[:2000]}")