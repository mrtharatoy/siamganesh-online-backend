import requests

SUPABASE_URL = "https://dgdbiounzoojphthypfl.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImRnZGJpb3Vuem9vanBodGh5cGZsIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NzM4NDY0ODMsImV4cCI6MjA4OTQyMjQ4M30.iTPXmp3SOev5ZxmmpXja0HsBkmB8k5aw8-_7INopOGU"

base = SUPABASE_URL.rstrip("/")
url = f"{base}/storage/v1/object/list/portfolio"
headers = {
    "apikey": SUPABASE_KEY, 
    "Authorization": f"Bearer {SUPABASE_KEY}"
}

def get_bucket_stats(prefix=""):
    payload = {"prefix": prefix, "limit": 1000, "offset": 0}
    r = requests.post(url, headers=headers, json=payload, timeout=10)
    
    if r.status_code != 200:
        return 0, 0
        
    data = r.json()
    count = 0
    size = 0
    
    for item in data:
        if item.get("id") is None: # It's a folder!
            folder_name = item.get("name")
            if folder_name and folder_name != ".emptyFolderPlaceholder":
                new_prefix = f"{prefix}{folder_name}/" if prefix else f"{folder_name}/"
                sub_count, sub_size = get_bucket_stats(new_prefix)
                count += sub_count
                size += sub_size
        else: # It's a file
            count += 1
            size += item.get("metadata", {}).get("size", 0)
            
    return count, size

c, s = get_bucket_stats("")
print("Count:", c)
print("Size MB:", s / (1024*1024))
