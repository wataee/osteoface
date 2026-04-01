import requests

API_URL = "https://monecle.com/api/"
API_ID = "47481"
API_KEY = "1bea80296687dd365208431c1c7a209a6f8a10fcd748ff6c071134e0597ccc70"

res = requests.post(API_URL, data={
    "method": "GetOrders",
    "id": API_ID,
    "key": API_KEY,
    "count": 5
})

print(res.json())