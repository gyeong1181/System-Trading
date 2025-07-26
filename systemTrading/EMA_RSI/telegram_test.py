from config import telegram_token, telegram_chat_id
import requests

# f-string 안에는 변수 이름만!
url = f"https://api.telegram.org/bot{7842018018:AAFgcQRqgUeXrX1du5MsPdpwcQZUj2QLJ2s}/sendMessage"

resp = requests.post(url, json={
    "chat_id": 2098940668,
    "text": "🟢 Telegram 알림 테스트 성공!"
})
print(resp.json())  
