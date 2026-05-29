import os
import json
import base64
import io
from google.oauth2.service_account import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

folder_id = "1ipmWf63dlv9MN76enBDAfmE0cuk7t5d3"
creds_file = 'google_credentials.json'

with open(creds_file, 'r') as f:
    creds_info = json.load(f)

scopes = ['https://www.googleapis.com/auth/drive.file']
creds = Credentials.from_service_account_info(creds_info, scopes=scopes)
service = build('drive', 'v3', credentials=creds, cache_discovery=False)

# create a dummy image (1x1 transparent png in base64)
b64_png = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="
file_data = base64.b64decode(b64_png)

file_metadata = {
    'name': 'test_upload.png',
    'parents': [folder_id]
}
media = MediaIoBaseUpload(io.BytesIO(file_data), mimetype='image/png', resumable=True)

try:
    gfile = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
    print("Success! File ID:", gfile.get('id'))
except Exception as e:
    print("Error:", e)
