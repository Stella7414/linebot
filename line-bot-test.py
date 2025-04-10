import os
import re
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, LocationMessage,
    TextSendMessage, ImageSendMessage
)

app = Flask(__name__)

# 🔐 記得替換成你自己的金鑰
line_bot_api = LineBotApi('WmbUAzI0q476afxlGFAI4uWPBwu2dAmtlij8/qafhL0ORORU3xzREMTUD1K20sQriV9M0KAqPYPtRGbSXB3JnsRn/0NQEifIua6/QOxOh87dXlFy60oQJ9Oy8kmIR+vVlaMd304tZAQSGkM0FaG1vQdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('dce8eedd82d6998f7ea5d5106e614c92')

GOOGLE_PLACES_API_KEY = 'AIzaSyBqbjGjjpt3Bxo9RB15DE4uVBmoBRlNXVM'
GOOGLE_MAPS_API_KEY = 'AIzaSyBqbjGjjpt3Bxo9RB15DE4uVBmoBRlNXVM' 

# 📍 記住使用者的最近位置
user_locations = {}

# 📍 文字查詢餐廳
def search_restaurants(location, keyword=None):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    query = f"{location} 餐廳"
    if keyword:
        query += f" {keyword}"  # 加上食物類型（如果有的話）
    params = {
        "query": query,
        "key": GOOGLE_PLACES_API_KEY,
        "language": "zh-TW",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            return ["😢 沒有找到相關餐廳，請換個關鍵字試試看！"]

        restaurants = sorted(data["results"], key=lambda r: r.get("rating", 0), reverse=True)[:3]
        messages = ["🍽 **熱門餐廳推薦** 🍽\n"]
        for idx, r in enumerate(restaurants, start=1):
            name = r.get("name", "未知餐廳")
            rating = r.get("rating", "無評分")
            address = r.get("formatted_address", "無地址資訊")
            status = r.get("business_status", "無營業資訊")
            place_id = r.get("place_id", "")

            photo_url = None
            if "photos" in r:
                photo_ref = r["photos"][0]["photo_reference"]
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_ref}&key={GOOGLE_PLACES_API_KEY}"

            reviews = get_reviews(place_id)

            msg = f"🏆 **{idx}. {name}**\n⭐ 評分：{rating}/5.0\n📍 地址：{address}\n🕒 營業狀況：{status}\n"
            if reviews:
                msg += f"💬 評論：{reviews}\n"
            msg += f"🚗 [導航](https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')})\n"
            messages.append(msg.strip())
            if photo_url:
                messages.append(photo_url)
        return messages

    except requests.exceptions.RequestException as e:
        return [f"❌ 無法獲取餐廳資訊：{e}"]

# 📍 位置查詢附近餐廳
def search_nearby_restaurants(lat, lng, keyword=None):
    url = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"
    params = {
        "location": f"{lat},{lng}",
        "radius": 1000,
        "type": "restaurant",
        "key": GOOGLE_PLACES_API_KEY,
        "language": "zh-TW"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if not data.get("results"):
            return ["😢 附近找不到餐廳，換個地點試試吧！"]

        # 篩選符合食物關鍵字（如果有的話）
        if keyword:
            data["results"] = [r for r in data["results"] if keyword in r.get("name", "")]

        restaurants = sorted(data["results"], key=lambda r: r.get("rating", 0), reverse=True)[:3]
        messages = ["📍 **你附近的熱門餐廳** 🍽\n"]
        for idx, r in enumerate(restaurants, start=1):
            name = r.get("name", "未知餐廳")
            rating = r.get("rating", "無評分")
            address = r.get("vicinity", "無地址資訊")
            place_id = r.get("place_id", "")

            photo_url = None
            if "photos" in r:
                photo_ref = r["photos"][0]["photo_reference"]
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_ref}&key={GOOGLE_PLACES_API_KEY}"

            reviews = get_reviews(place_id)

            msg = f"🏅 **{idx}. {name}**\n⭐ 評分：{rating}\n📍 地址：{address}\n"
            if reviews:
                msg += f"💬 評論：{reviews}\n"
            msg += f"🚗 [導航](https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')})\n"
            messages.append(msg.strip())
            if photo_url:
                messages.append(photo_url)
        return messages

    except requests.exceptions.RequestException as e:
        return [f"❌ 查詢失敗：{e}"]

# 🗣 查詢評論
def get_reviews(place_id):
    url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": GOOGLE_PLACES_API_KEY,
        "language": "zh-TW"
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        reviews = data.get("result", {}).get("reviews", [])
        for r in reviews:
            if 'zh' in r.get("language", ""):
                return r.get("text")
        return reviews[0]["text"] if reviews else None
    except requests.exceptions.RequestException:
        return None

# 📤 共用訊息發送函數
def send_messages(event, messages):
    first_message_sent = False
    for msg in messages:
        if msg.startswith("http"):  # 圖片 URL
            line_bot_api.push_message(
                event.source.user_id,
                ImageSendMessage(original_content_url=msg, preview_image_url=msg)
            )
        else:
            text_message = TextSendMessage(text=msg)
            if not first_message_sent:
                line_bot_api.reply_message(event.reply_token, text_message)
                first_message_sent = True
            else:
                line_bot_api.push_message(event.source.user_id, text_message)

# 📍 記錄使用者的最後位置
@handler.add(MessageEvent, message=LocationMessage)
def handle_location(event):
    lat = event.message.latitude
    lng = event.message.longitude
    user_locations[event.source.user_id] = (lat, lng)  # 記住位置
    messages = ["👍 已記錄您的位置！請輸入「附近 食物」來查詢附近餐廳。"]
    send_messages(event, messages)

# 📝 處理文字訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text.strip()
    user_id = event.source.user_id

    if user_input.startswith("附近 "):  # 查詢附近餐廳，並根據關鍵字過濾
        keyword = user_input[2:].strip()  # 取得食物關鍵字（例如：拉麵）
        if user_id in user_locations:
            lat, lng = user_locations[user_id]
            messages = search_nearby_restaurants(lat, lng, keyword)
        else:
            messages = ["❌ 您尚未提供位置，請先發送您的位置。"]
    
    elif len(user_input) >= 2:
        messages = search_restaurants(user_input)  # 查詢某個地點的餐廳
    else:
        messages = ["❌ 請輸入 **城市名稱 + 美食類型**（例如：「台北燒肉」），或使用 `附近 食物` 查詢附近餐廳。"]

    send_messages(event, messages)

# 📬 LINE Webhook Endpoint
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    except Exception as e: 
