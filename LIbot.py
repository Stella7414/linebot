import os
import requests
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage, ImageSendMessage

app = Flask(__name__)

# 🚀 填入你的 LINE Bot API Key
line_bot_api = LineBotApi('WmbUAzI0q476afxlGFAI4uWPBwu2dAmtlij8/qafhL0ORORU3xzREMTUD1K20sQriV9M0KAqPYPtRGbSXB3JnsRn/0NQEifIua6/QOxOh87dXlFy60oQJ9Oy8kmIR+vVlaMd304tZAQSGkM0FaG1vQdB04t89/1O/w1cDnyilFU=')
handler = WebhookHandler('dce8eedd82d6998f7ea5d5106e614c92')

# 🚀 填入你的 Google Places API Key
GOOGLE_PLACES_API_KEY = 'AIzaSyBqbjGjjpt3Bxo9RB15DE4uVBmoBRlNXVM'
GOOGLE_MAPS_API_KEY = 'AIzaSyBqbjGjjpt3Bxo9RB15DE4uVBmoBRlNXVM'

# 📍 Google Places API 查詢函數（顯示最多 3 間餐廳）
def search_restaurants(location):
    url = "https://maps.googleapis.com/maps/api/place/textsearch/json"
    params = {
        "query": f"{location} 餐廳",
        "key":GOOGLE_PLACES_API_KEY ,
        "language": "zh-TW",
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "results" not in data or not data["results"]:
            return ["😢 沒有找到相關餐廳，請換個關鍵字試試看！"]

        restaurants = sorted(data["results"], key=lambda r: r.get("rating", 0), reverse=True)[:3]

        messages = ["🍽 **熱門餐廳推薦** 🍽\n"]
        for index, r in enumerate(restaurants, start=1):
            name = r.get("name", "未知餐廳")
            rating = r.get("rating", "無評分")
            address = r.get("formatted_address", "無地址資訊")
            business_status = r.get("business_status", "無營業資訊")
            place_id = r.get("place_id", "")

            # 獲取照片
            photo_url = None
            if "photos" in r:
                photo_reference = r["photos"][0]["photo_reference"]
                photo_url = f"https://maps.googleapis.com/maps/api/place/photo?maxwidth=800&photoreference={photo_reference}&key={GOOGLE_PLACES_API_KEY}"

            # 獲取評論
            reviews = get_reviews(place_id)

            message = f"🏆 **{index}. {name}**\n"
            message += f"⭐ 評分：{rating}/5.0\n"
            message += f"📍 地址：{address}\n"
            message += f"🕒 營業狀況：{business_status}\n"
            if reviews:
                message += f"💬 最佳評論：{reviews}\n"
            message += f"🚗 [Google Maps 導航](https://www.google.com/maps/search/?api=1&query={address.replace(' ', '+')})\n"

            messages.append(message.strip())  # 加入文字訊息

            if photo_url:
                messages.append(photo_url)  # 直接加入圖片 URL

        return messages

    except requests.exceptions.RequestException as e:
        return [f"❌ 無法獲取餐廳資訊：{e}"]

# 🔄 獲取餐廳評論
def get_reviews(place_id):
    review_url = "https://maps.googleapis.com/maps/api/place/details/json"
    params = {
        "place_id": place_id,
        "key": GOOGLE_PLACES_API_KEY,
        "language": "zh-TW"
    }

    try:
        response = requests.get(review_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "result" in data and "reviews" in data["result"]:
            reviews = data["result"]["reviews"]
            for review in reviews:
                if 'zh' in review['language']:
                    return review['text']
            return reviews[0]['text'] if reviews else None
        return None
    except requests.exceptions.RequestException:
        return None

# 🛣 查詢路線（Google Directions API）
def get_route(origin, destination):
    url = f"https://maps.googleapis.com/maps/api/directions/json"
    params = {
        "origin": origin,
        "destination": destination,
        "mode": "walking",  # 可用 driving、transit、bicycling
        "key": GOOGLE_MAPS_API_KEY
    }
    response = requests.get(url, params=params).json()

    if response["status"] == "OK":
        steps = response["routes"][0]["legs"][0]["steps"]
        directions = "\n".join([step["html_instructions"].replace("<b>", "").replace("</b>", "") for step in steps])
        return directions
    else:
        return "🚫 無法取得路線，請確認地點是否正確。"

# 📨 處理 LINE 訊息
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_input = event.message.text.strip()

    if user_input.startswith("路線 "):  # 查詢路線，例如："路線 台北車站 雄大餐廳"
        try:
            _, origin, destination = user_input.split()
            route_info = get_route(origin, destination)
            reply_text = f"🗺 **從 {origin} 到 {destination} 的建議路線**\n{route_info}"
        except:
            reply_text = "❌ 請輸入格式：**路線 出發地 目的地**"
        messages = [reply_text]

    elif len(user_input) >= 2:  # 查詢餐廳
        messages = search_restaurants(user_input)
    else:
        messages = ["❌ 請輸入 **城市名稱 + 美食類型**（例如：「台北燒肉」），或使用 `路線 出發地 目的地` 查詢路線。"]

    # **發送訊息**
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

# 📌 Line Bot Webhook 設定
@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers.get('X-Line-Signature', '')
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return 'OK'

# 🔥 啟動 Flask 應用程式
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
