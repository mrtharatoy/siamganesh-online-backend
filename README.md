# 🕉️ Siamganesh Online Backend

<div align="center">

[![Python Version](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org/)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com/)
[![Supabase](https://img.shields.io/badge/Supabase-Database-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white)](https://supabase.com/)
[![Gemini](https://img.shields.io/badge/Google_Gemini-AI-4285F4?style=for-the-badge&logo=google-gemini&logoColor=white)](https://deepmind.google/technologies/gemini/)
[![Facebook API](https://img.shields.io/badge/Facebook_Graph_API-v19.0-1877F2?style=for-the-badge&logo=facebook&logoColor=white)](https://developers.facebook.com/)

**ระบบ Backend อัตโนมัติ (Flask) สำหรับจัดการและส่งมอบภาพพิธีกรรมทางศาสนา/ความเชื่อ ผ่าน Facebook Messenger Webhook**  
รองรับการแยกทำงานตามเพจต้นทางแบบ Multi-Page ได้แก่ **เพจมหาบูชา** และ **เพจมูเตทีม** พร้อมผสานการทำงานกับ Supabase และ Google Gemini AI

</div>

---

## 🌟 ฟีเจอร์เด่น (Key Features)

*   **Multi-Page Messenger Support**: รับข้อความ Webhook จาก Facebook Messenger และแยกกระบวนการทำงานตาม Page ID ได้อย่างแม่นยำ
*   **Automated Image Delivery**: ตรวจจับรูปแบบข้อความและรหัสบริการ เพื่อส่งภาพถาดถวาย/ภาพพิธีกรรมที่บันทึกไว้ใน GitHub กลับไปให้ผู้ใช้งานทันที
*   **Supabase Database Integration**: ดึงข้อมูลผู้ศรัทธา (ชื่อภาษาไทย/ชื่อร่วม) จากระบบจองอัตโนมัติด้วยรหัสอ้างอิง 12 หลัก
*   **Personalized AI Blessing (Gemini 1.5 Flash)**: ขับเคลื่อนด้วยพลัง AI ในการรังสรรค์และสร้างสรรค์ข้อความขอบคุณและคำอวยพรอันเป็นสิริมงคลเฉพาะบุคคลตามบริบทชื่อผู้ศรัทธาอย่างนอบน้อมและดูเป็นธรรมชาติ
*   **In-Memory Image Caching**: ลดความหน่วงและประหยัด API Rate Limit ของ GitHub ด้วยระบบ Cache ชื่อไฟล์และโครงสร้าง URL ภาพในหน่วยความจำ
*   **Rich API Endpoints**: มี API เพื่อใช้ควบคุมและทำงานร่วมกับระบบภายนอก เช่น การอัปโหลดภาพด้วย Base64 การสืบค้นภาพ และการรีโหลด Cache

---

## 🏗️ สถาปัตยกรรมระบบ (System Architecture)

```mermaid
graph TD
    User([👤 ผู้ใช้งาน / ลูกค้า]) -->|ส่งข้อความ / รหัส| FB[💬 Facebook Messenger]
    FB -->|Webhook POST /| Flask[🌶️ Flask Webhook App]
    
    subgraph Webhook Router
        Flask -->|Page: มหาบูชา| MB[📿 Flow มหาบูชา]
        Flask -->|Page: มูเตทีม| MT[🔮 Flow มูเตทีม]
    end

    subgraph มหาบูชา Flow
        MB -->|ดักจับรหัสองค์เทพ| RegexMB{ตรงกับ Regex?}
        RegexMB -->|ใช่| CacheMB[📂 ค้นหารูปใน GitHub Cache]
        CacheMB -->|พบภาพ| SendMB[🖼️ ส่งรูปภาพบูชาผ่าน Graph API]
        RegexMB -->|ไม่พบ/ไม่ตรง| AdminMB[👤 แจ้งเตือนแอดมิน]
    end

    subgraph มูเตทีม Flow
        MT -->|ดักจับรหัสจอง 12 หลัก| RegexMT{ตรงกับ Regex?}
        RegexMT -->|ใช่| CacheMT[📂 ค้นหารูปใน GitHub Cache]
        CacheMT -->|พบภาพ| SB[⚡ ดึงชื่อจาก Supabase]
        SB -->|ได้ชื่อผู้ศรัทธา| Gemini[🤖 Google Gemini AI]
        Gemini -->|สร้างข้อความอนุโมทนาเฉพาะบุคคล| SendMT[🖼️ ส่งรูปภาพ + ข้อความขอบคุณผ่าน Graph API]
        RegexMT -->|ไม่ตรง| IgnoreMT[🔇 ข้าม]
        CacheMT -->|ไม่พบภาพ| WaitMT[⏳ ส่งข้อความให้รอคิวทำพิธี]
    end

    subgraph GitHub Storage & Cache
        GitHub[🐙 GitHub Repository] -->|GitHub API| LoadCache[🔄 In-Memory Cache]
        LoadCache -.-> CacheMB
        LoadCache -.-> CacheMT
    end
```

---

## 📂 โครงสร้างโปรเจกต์ (Project Structure)

```bash
siamganesh-online-backend/
├── app.py              # แอปพลิเคชันหลัก (Flask) และจุดรวม Webhook & APIs
├── requirements.txt    # รายการ dependencies ที่จำเป็นสำหรับรันระบบ
├── README.md           # เอกสารแนะนำโปรเจกต์และการใช้งาน
└── images/             # โฟลเดอร์เก็บภาพถาดถวายและผลลัพธ์พิธีกรรม (Sync ไปยัง GitHub)
    ├── mahabucha/      # ภาพถาดถวายของเพจมหาบูชา (จัดเก็บในชื่อ deity_code.jpg)
    └── muteteam/       # ภาพถาดถวายของเพจมูเตทีม (จัดเก็บในชื่อ booking_code_index.webp)
```

---

## ⚙️ การตั้งค่าระบบ (Configuration & Env)

โปรเจกต์นี้ทำงานโดยใช้ค่ากำหนดต่าง ๆ ผ่าน Environment Variables ด้านล่างนี้คือรายการตัวแปรที่จำเป็นต้องกำหนดก่อนเริ่มทำงาน:

| ชื่อตัวแปร | คำอธิบายเพิ่มเติม | ตัวอย่างค่า |
|:---|:---|:---|
| `MAHABUCHA_PAGE_ID` | หมายเลข ID ของ Facebook Page (มหาบูชา) | `102938475612345` |
| `MAHABUCHA_TOKEN` | Page Access Token ที่ได้จาก Facebook Developer (มหาบูชา) | `EAABw...` |
| `MUTETEAM_PAGE_ID` | หมายเลข ID ของ Facebook Page (มูเตทีม) | `564738291012345` |
| `MUTETEAM_TOKEN` | Page Access Token ที่ได้จาก Facebook Developer (มูเตทีม) | `EAABw...` |
| `VERIFY_TOKEN` | โทเค็นความปลอดภัยที่ตั้งเอง เพื่อกรอกในหน้า Messenger Webhook Setup | `SiamGaneshVerifyToken2026` |
| `GITHUB_TOKEN` | GitHub Personal Access Token (แนะนำแบบ Fine-grained หรือ Classic ที่มีสิทธิ์อ่าน/เขียน content) | `ghp_abcdef...` |
| `GEMINI_API_KEY` | Google AI Studio API Key สำหรับเรียกใช้โมเดล Gemini | `AIzaSy...` |
| `SUPABASE_URL` | URL ของโครงการ Supabase ของคุณ | `https://xxxx.supabase.co` |
| `SUPABASE_KEY` | Supabase API Key (แนะนำ Service Role Key ในกรณีที่ไม่อยู่ภายใต้ RLS หรือ Anon Key) | `eyJhbGciOi...` |

---

## 🔮 รูปแบบของรหัสและการจับคู่ภาพ (Code Pattern Matching)

ระบบจะใช้ Regular Expression (Regex) ในการตรวจสอบความถูกต้องของรหัสที่ลูกค้าพิมพ์เข้ามาผ่านแชท ดังนี้:

### 📿 1. เพจมหาบูชา (Mahabucha)
*   **เป้าหมาย**: จับคู่รูปภาพองค์เทพรายบุคคล
*   **รูปแบบ Regex**: `(?:269|999)[a-z]{2}(?:0[1-9]|1[0-9]|20)\d{3}`
*   **ตัวอย่างรหัสที่ถูกต้อง**: `269aa01234`, `999bc15001`
*   **การจับคู่ไฟล์**: ค้นหาไฟล์ใน `images/mahabucha/` ที่ชื่อไฟล์ไม่มี extension ตรงกับรหัส เช่น `269aa01234.jpg`

### 🔮 2. เพจมูเตทีม (Muteteam)
*   **เป้าหมาย**: จับคู่ผลลัพธ์ภาพพิธีตามรหัสจอง 12 หลัก
*   **รูปแบบ Regex**: รหัสจอง 12 หลัก (YYMMDDHHmmss) เช่น `260519142238`
*   **การจับคู่ไฟล์**: ดึงภาพทั้งหมดที่มีคำนำหน้า (Prefix) ตรงกับรหัสจองและเรียงลำดับดัชนี เช่น `260519142238_1.webp`, `260519142238_2.webp` เป็นต้น

---

## 🚀 การเริ่มต้นใช้งาน (Local Development)

### 1. ติดตั้ง Dependencies
เปิดเทอร์มินัลในโฟลเดอร์โปรเจกต์ จากนั้นรันคำสั่งสร้าง Virtual Environment และติดตั้ง library ที่จำเป็น:

```bash
# สร้างและเปิดใช้งาน Virtual Environment (ทางเลือก)
python3 -m venv venv
source venv/bin/activate  # สำหรับ Mac/Linux
# venv\Scripts\activate   # สำหรับ Windows

# ติดตั้งแพ็กเกจ
pip install -r requirements.txt
```

### 2. ตั้งค่า Environment Variables
บนระบบปฏิบัติการ Mac / Linux คุณสามารถ Export ตัวแปรได้ดังนี้:

```bash
export MAHABUCHA_PAGE_ID="your_mahabucha_page_id"
export MAHABUCHA_TOKEN="your_mahabucha_page_access_token"
export MUTETEAM_PAGE_ID="your_muteteam_page_id"
export MUTETEAM_TOKEN="your_muteteam_page_access_token"
export VERIFY_TOKEN="your_webhook_verify_token"
export GITHUB_TOKEN="your_github_token"
export GEMINI_API_KEY="your_gemini_api_key"
export SUPABASE_URL="your_supabase_url"
export SUPABASE_KEY="your_supabase_key"
```

*(สำหรับระบบปฏิบัติการ Windows ให้ใช้คำสั่ง `set` แทน `export`)*

### 3. รันระบบสำหรับการพัฒนา
```bash
python app.py
```
เมื่อรันสำเร็จ ระบบจะเริ่มทำงานที่ `http://127.0.0.1:5000` โดยจะดึงข้อมูลรูปภาพจาก GitHub มาบันทึกใน Cache เป็นครั้งแรกโดยอัตโนมัติ

---

## 🌐 API Reference (รายการ Endpoint)

### 1. Webhook Endpoint
ใช้สำหรับผูกต่อกับระบบ Facebook Webhook

*   **Endpoint**: `/`
*   **GET**: ใช้สำหรับยืนยันตน (Verification)
*   **POST**: ใช้สำหรับรับข้อมูล (Messaging Events) จากทาง Facebook เมื่อมีข้อความแชทใหม่เข้ามา

---

### 2. ค้นหารูปภาพตามรหัส
*   **Endpoint**: `/api/search`
*   **Method**: `GET`
*   **Parameters**:
    *   `page`: ระบุ `mahabucha` หรือ `muteteam`
    *   `code`: รหัสที่ต้องการค้นหา
*   **ตัวอย่างการเรียก**:
    `GET http://localhost:5000/api/search?page=muteteam&code=260519142238`
*   **ผลลัพธ์ (พบข้อมูล):**
    ```json
    {
      "found": true,
      "results": [
        {
          "code": "260519142238_1",
          "image_url": "https://raw.githubusercontent.com/mrtharatoy/siamganesh-online-backend/main/images/muteteam/260519142238_1.webp"
        }
      ],
      "count": 1
    }
    ```

---

### 3. อัปโหลดภาพพิธีเข้าระบบ (GitHub Storage)
*   **Endpoint**: `/api/upload-image`
*   **Method**: `POST`
*   **Request Body**:
    ```json
    {
      "booking_code": "260519142238",
      "images": [
        { "index": 1, "ext": "webp", "data": "base64_encoded_image_data_here" },
        { "index": 2, "ext": "webp", "data": "base64_encoded_image_data_here" }
      ]
    }
    ```
*   **ผลลัพธ์ (สำเร็จ):**
    ```json
    {
      "success": true,
      "uploaded": ["260519142238_1.webp", "260519142238_2.webp"],
      "errors": [],
      "message": "อัปโหลดสำเร็จ 2/2 รูป"
    }
    ```

---

### 4. รีโหลด Cache รูปภาพจาก GitHub
สั่งการอัปเดตข้อมูลรายชื่อไฟล์ภาพจาก GitHub Repository ใหม่ด้วยวิธีเบื้องหลัง (Background Thread)

*   **Endpoint**: `/api/reload`
*   **Method**: `POST`
*   **ผลลัพธ์:**
    ```json
    {
      "message": "กำลัง reload cache..."
    }
    ```

---

### 5. สร้างข้อความส่งมอบภาพพิธีด้วย AI
สร้างประโยคอวยพรและอนุโมทนาขอบคุณส่วนตัว โดยอิงข้อมูลจากฐานข้อมูล Supabase และรังสรรค์ด้วย Gemini

*   **Endpoint**: `/api/generate-message`
*   **Method**: `GET`
*   **Parameters**:
    *   `booking_code`: รหัสการจอง 12 หลัก
*   **ตัวอย่างการเรียก**:
    `GET http://localhost:5000/api/generate-message?booking_code=260519142238`
*   **ผลลัพธ์:**
    ```json
    {
      "success": true,
      "booking_code": "260519142238",
      "person1_name": "สมชาย",
      "person2_name": "สมหญิง",
      "message": "📸 ขออนุญาตส่งมอบความสิริมงคลแด่คุณสมชายและคุณสมหญิงครับ ร่วมอนุโมทนาบุญและรับชมภาพบรรยากาศอันเป็นมงคลจากพิธีนี้ได้เลยนะครับ ขอเทวานุภาพคุ้มครองดลบันดาลให้ประสบแต่ความเจริญรุ่งเรืองครับ 🙏✨"
    }
    ```

---

### 6. ทดสอบความพร้อมเชื่อมต่อ Gemini API (Debug)
*   **Endpoint**: `/api/debug-gemini`
*   **Method**: `GET`
*   **Parameters**:
    *   `booking_code`: (ไม่บังคับ, ค่าเริ่มต้นคือ `TEST001`)

---

## 📦 การนำขึ้นใช้งานจริง (Production Deployment)

ในการทำงานจริง แนะนำให้รันแอปพลิเคชันด้วย **WSGI Server** เช่น `gunicorn` เพื่อเพิ่มประสิทธิภาพและความเสถียรในการรองรับ Concurrent Requests

### ตัวอย่างการติดตั้งและเริ่มทำงานด้วย Gunicorn:
```bash
# ติดตั้ง Gunicorn
pip install gunicorn

# รันเซิร์ฟเวอร์ Binding ไปยังพอร์ตที่ต้องการ
gunicorn app:app --bind 0.0.0.0:5000 --workers 4 --threads 2 --timeout 60
```

### การ Deploy บน Cloud Platforms:
*   **Render / Railway / Fly.io**: สามารถเชื่อมต่อ Repository นี้ และตั้งค่า environment variables ในเมนู Dashboard และกำหนด Start Command เป็น:
    `gunicorn app:app --bind 0.0.0.0:$PORT`
*   **Docker Container**: สามารถสร้าง `Dockerfile` สำหรับติดตั้ง dependencies และสั่งรันเซิร์ฟเวอร์เพื่อให้มีความสม่ำเสมอในทุกสภาพแวดล้อมระบบปฏิบัติการ

---

## 🛠️ รายการ Libraries ที่ใช้ (Dependencies)

*   **Flask & Flask-CORS**: จัดการ Web Server และ Cross-Origin Resource Sharing
*   **requests**: จัดการ HTTP Calls ส่งภาพและเชื่อมประสานกับ GitHub API, Gemini API, และ Supabase API
*   **gunicorn**: รันเว็บแอปเพื่อเพิ่มความสามารถของเกตเวย์เซิร์ฟเวอร์ในขั้นตอนการใช้งานจริง (Production)

---

## ⚖️ สัญญาอนุญาต (License)

โปรเจกต์นี้ได้รับการพัฒนาเพื่ออำนวยความสะดวกในธุรกิจและการจัดการภายในของแบรนด์ **สยามคเณศ (Siamganesh)**
