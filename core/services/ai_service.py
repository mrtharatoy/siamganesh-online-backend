"""
Gemini-backed message generation, extracted from app.py (SG-B-102).
Logic unchanged from the original app.py function of the same name --
only the import source for GEMINI_API_KEY moved.
"""
from config import GEMINI_API_KEY
from core.clients.gemini_client import generate_content


def generate_thank_you_message(booking_code, person1_name=None, person2_name=None):
    def fallback():
        names = person1_name or "ผู้มีจิตศรัทธา"
        if person2_name:
            names = f"{person1_name}และ{person2_name}"
        return (
            f"[PHOTO] ขออนุญาตส่งมอบความสิริมงคลแด่คุณ{names}ครับ "
            f"ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ 'มูเตทีม' นะครับ "
        )

    if not GEMINI_API_KEY:
        return fallback()

    if person1_name and person2_name:
        name_ctx = f"ผู้ศรัทธาชื่อ {person1_name} และ {person2_name} (มาด้วยกัน 2 คน)"
    elif person1_name:
        name_ctx = f"ผู้ศรัทธาชื่อ {person1_name}"
    else:
        name_ctx = "ผู้มีจิตศรัทธา"

    prompt = (
        "คุณเป็นผู้ดูแลเพจ มูเตทีม ที่ให้บริการฝากถวายของแก่องค์เทพครับ\n\n"
        f"สร้างข้อความขอบคุณและส่งมอบภาพพิธีให้ {name_ctx}\n"
        "เงื่อนไข:\n"
        "- ต้องกล่าวถึงชื่อของผู้ศรัทธาทุกคน (อย่าลืม!)\n"
        "- สำนวนสุภาพ อ่อนน้อม ศักดิ์สิทธิ์ อบอุ่น\n"
        "- บอกว่ากำลังส่งภาพจากพิธีกรรม\n"
        "- แนะนำให้ติดตามเพจ มูเตทีม\n"
        "- ความยาว 2-3 ประโยค ไม่ยาวเกินไป\n"
        "- ลงท้ายด้วย \n"
        "- ตอบเฉพาะข้อความที่จะส่ง ไม่ต้องมีคำอธิบายเพิ่มเติม"
    )

    try:
        payload = {
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "temperature":     0.9,
                "maxOutputTokens": 300,
            },
        }
        r = generate_content("gemini-1.5-flash", payload, api_version="v1", timeout=15)
        if r.status_code == 200:
            msg = r.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"Gemini msg for {booking_code}: {msg[:50]}...")
            return msg
        else:
            print(f"Gemini error {r.status_code}: {r.text[:200]}")
    except Exception as e:
        print(f"Gemini API error: {e}")

    return fallback()
