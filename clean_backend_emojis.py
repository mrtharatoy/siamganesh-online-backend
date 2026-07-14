import re

replacements = {
    '🔄': '[SYNC]',
    '💬': '[FB]',
    '🧠': '[PROCESS]',
    '🚀': '[DISPATCH]',
    '🔍': '[SEARCH]',
    '📂': '[FILE]',
    '📤': '[UPLOAD]',
    '🗑️': '[DELETE]',
    '💌': '[MAIL]',
    '🔧': '[DEBUG]',
    '📲': '[NOTIFY]',
    '📰': '[NEWS]',
    '📊': '[STATS]',
    '📸': '[PHOTO]',
    '🚨': '[ALERT]',
    '📌': '[PIN]',
    '🔗': '[LINK]',
    '💡': '[HINT]',
    '🕒': '[TIMER]',
    '🔔': '[NOTIFY]',
    '📅': '[DATE]',
    '📈': '[TREND]',
    '🙏✨': '',
    '🙏': '',
    '✨': '',
    '🟢': '[OK]',
    '🔵': '[INFO]',
    '🟣': '[INFO]',
    '📩': '[MSG]'
}

with open('app.py', 'r', encoding='utf-8') as f:
    content = f.read()

for k, v in replacements.items():
    content = content.replace(k, v)

with open('app.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Backend emojis removed and replaced with professional tags.")
