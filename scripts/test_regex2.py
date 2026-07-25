import re
text = "รหัสภาพ\n999aa109584"
pattern_regex = r'\b\d+\s*[a-z]{2}\s*\d+\b'
print(re.findall(pattern_regex, text))
