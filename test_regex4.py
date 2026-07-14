import re
pattern = r'(?<!\d)\d+\s*[a-z]{2}\s*\d+(?!\d)'

tests = [
    "รหัสภาพ999aa109584",
    "999aa109584ครับ",
    "รหัส999aa109584ค่ะ",
    "รหัสภาพ\n999aa109584",
    "รหัส 999aa109584",
]

for t in tests:
    print(t, "->", re.findall(pattern, t))
