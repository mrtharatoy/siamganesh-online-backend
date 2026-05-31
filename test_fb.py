import requests
from bs4 import BeautifulSoup
import sys

headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Mobile/15E148 Safari/604.1'}
url = f"https://m.facebook.com/{sys.argv[1]}"
r = requests.get(url, headers=headers, timeout=10, allow_redirects=True)
soup = BeautifulSoup(r.text, 'html.parser')
title = soup.find('title')
print(f"Title: {title.text if title else 'No title'}")
