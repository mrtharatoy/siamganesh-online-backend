import re
text = "รหัสภาพ\n999AA109584"
pattern_regex = r'\b\d+\s*[a-z]{2}\s*\d+\b'
matches = re.findall(pattern_regex, text.lower())
print("Matches:", matches)
