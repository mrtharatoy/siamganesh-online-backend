"""
Thank-you message generation for delivered ceremony photos, extracted
from app.py (SG-B-102). Previously called Gemini to generate a varied
message when GEMINI_API_KEY was configured, falling back to a static
template otherwise; the Gemini branch has been removed and this now
always returns the template message.
"""


def generate_thank_you_message(booking_code, person1_name=None, person2_name=None):
    names = person1_name or "ผู้มีจิตศรัทธา"
    if person2_name:
        names = f"{person1_name}และ{person2_name}"
    return (
        f"[PHOTO] ขออนุญาตส่งมอบความสิริมงคลแด่คุณ{names}ครับ "
        f"ร่วมอนุโมทนาและรับชมภาพบรรยากาศได้ที่เพจ 'มูเตทีม' นะครับ "
    )
