import os
import requests

GITHUB_TOKEN = os.environ.get('GITHUB_TOKEN')
GITHUB_USERNAME = "mrtharatoy"
REPO_NAME = "siamganesh-online-backend"
BRANCH = "main"

headers = {"Authorization": f"token {GITHUB_TOKEN}", "Accept": "application/vnd.github.v3+json"} if GITHUB_TOKEN else {}
api_url = f"https://api.github.com/repos/{GITHUB_USERNAME}/{REPO_NAME}/contents/images/mahabucha?ref={BRANCH}"
print("Fetching:", api_url)
r = requests.get(api_url, headers=headers)
print("Status Code:", r.status_code)
print("Response:", r.text[:200])
