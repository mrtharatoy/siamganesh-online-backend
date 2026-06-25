import requests, os, json
from dotenv import load_dotenv
load_dotenv()
api_key = os.environ.get('GEMINI_API_KEY')
url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={api_key}"
payload1 = {
    "contents": [{"parts": [{"text": "Hello, return JSON"}]}],
    "generationConfig": {"response_mime_type": "application/json"}
}
payload2 = {
    "contents": [{"parts": [{"text": "Hello, return JSON"}]}],
    "generationConfig": {"responseMimeType": "application/json"}
}
print("payload1:")
print(requests.post(url, json=payload1).text)
print("payload2:")
print(requests.post(url, json=payload2).text)
