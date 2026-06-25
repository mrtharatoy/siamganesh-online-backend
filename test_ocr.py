import requests
import json
import base64
import os

key = ""
with open('.env', 'r') as f:
    for line in f:
        if line.startswith('GEMINI_API_KEY'):
            key = line.split('=')[1].strip().strip('"').strip("'")

def test():
    with open('../siamganesh-online-frontend/public/images/og-image.jpg', 'rb') as f:
        img_data = base64.b64encode(f.read()).decode('utf-8')

    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "text": "Perform OCR on this image. Extract ALL text you can see, especially all numbers and English characters. Just return the raw extracted text without any formatting or explanation."
                    },
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": img_data
                        }
                    }
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0.1
        }
    }
    
    r = requests.post(url, json=payload, timeout=20)
    print("STATUS", r.status_code)
    try:
        print(json.dumps(r.json(), indent=2))
    except:
        print(r.text)

test()
