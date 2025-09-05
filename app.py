from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit
import asyncio
import threading
import json
import os
from datetime import datetime
from telethon import TelegramClient

app = Flask(__name__)
app.config['SECRET_KEY'] = 'telegram-gui-secret'
socketio = SocketIO(app, cors_allowed_origins="*")

# متغيرات النظام
client = None
is_running = False
current_settings = {}

# المجموعات المستهدفة
GROUPS = [
    "skdjfu", "Maths_genius2", "mtager545", "sultanu1999", "salla_pool",
    "Taif64", "groupIAU", "universty_taif11", "ksucpy", "Tu_English2",
    "bsfmisk", "httpsLjsIIb3S3nIwMzVk", "bdydbeu", "sdgghjklv",
    "DigitalSAMAA", "tabuk_2022", "KearneyMiddleEast", "jazanh12",
    "YouthGrowthProgramYGP"
]

def log_message(message):
    """إرسال رسالة إلى السجل"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = f"[{timestamp}] {message}"
    socketio.emit('log_update', {'message': log_entry})
    print(log_entry)

def update_status(status):
    """تحديث حالة النظام"""
    socketio.emit('status_update', {'status': status})

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/save_settings', methods=['POST'])
def save_settings():
    """حفظ الإعدادات"""
    global current_settings
    try:
        current_settings = request.get_json()
        
        # حفظ في ملف
        with open("web_settings.json", "w", encoding="utf-8") as f:
            json.dump(current_settings, f, ensure_ascii=False, indent=2)
            
        log_message("✅ تم حفظ الإعدادات بنجاح")
        return jsonify({"success": True, "message": "تم حفظ الإعدادات"})
    except Exception as e:
        log_message(f"❌ خطأ في حفظ الإعدادات: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/load_settings')
def load_settings():
    """تحميل الإعدادات"""
    try:
        if os.path.exists("web_settings.json"):
            with open("web_settings.json", "r", encoding="utf-8") as f:
                settings = json.load(f)
            return jsonify({"success": True, "settings": settings})
        else:
            # إعدادات افتراضية
            default_settings = {
                "phone": "",
                "api_id": "",
                "api_hash": "",
                "code": "",
                "password": "",
                "interval": "5",
                "message": """🎯 *مركز سرعة إنجاز* 📚💻
كل ما تحتاجه في *دراستك الجامعية، التقنية، وحتى خدماتك الطبية*… في مكان واحد!

✅ *خدمات أكاديمية وبحثية:*

* إعداد رسائل الماجستير والدكتوراه باحترافية.
* اقتراح عناوين وخطط بحث متميزة.
* توفير المراجع والدراسات السابقة.
* إعداد أبحاث النشر والترقية.
* التحليل الإحصائي والتدقيق اللغوي.

✅ *خدمات طلابية:*

* حل الواجبات والاختبارات (كويز – ميد – فاينل).
* تلخيص المقررات.
* تصميم عروض *PowerPoint* احترافية.
* إعداد مشاريع التخرج والتقارير.

✅ *خدمات تقنية وبرمجية:*

* تصميم وبرمجة المواقع والمتاجر الإلكترونية.
* تطوير أنظمة إدارة المهام والهيكل التنظيمي.
* تحسين محركات البحث (SEO) والدعم الفني.

✅ *خدمات تصميم وترجمة:*

* تصميم السيرة الذاتية والبروشورات.
* ترجمة معتمدة للمستندات والأبحاث.

---

🚨 *سكليفك الطبي… أسرع مما تتخيل!*🚨
📍 *مركز سرعة إنجاز – خبرة وأمانة وسرعة في خدمتك*

🩺 سواء كنت *عسكري – مدني – طالب*…
📄 نوفر لك خدمة *استخراج سكليف صحتي* بكل احترافية وفي وقت قياسي، بدون عناء أو تأخير!

✨ *مميزات خدمتنا:*
✅ سرعة إنجاز غير مسبوقة ⏱
✅ دقة ومطابقة للمواصفات المطلوبة 📋
✅ تعامل سري وآمن 100% 🔒
✅ خدمة في جميع مناطق المملكة 🇸🇦

---

📞 *للتواصل والاستفسار:*
📲 واتساب: *https://wa.me/+966510349663*"""
            }
            return jsonify({"success": True, "settings": default_settings})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/start_sending', methods=['POST'])
def start_sending():
    """بدء الإرسال"""
    global is_running, current_settings
    
    try:
        current_settings = request.get_json()
        
        # التحقق من البيانات
        required_fields = ['phone', 'api_id', 'api_hash', 'code']
        for field in required_fields:
            if not current_settings.get(field):
                return jsonify({"success": False, "error": f"حقل {field} مطلوب"})
        
        if is_running:
            return jsonify({"success": False, "error": "النظام يعمل بالفعل"})
        
        is_running = True
        update_status("يعمل")
        log_message("🚀 بدء نظام الإرسال...")
        
        # تشغيل في خيط منفصل
        thread = threading.Thread(target=run_telegram_client, daemon=True)
        thread.start()
        
        return jsonify({"success": True, "message": "تم بدء النظام"})
        
    except Exception as e:
        log_message(f"❌ خطأ في بدء النظام: {str(e)}")
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/stop_sending', methods=['POST'])
def stop_sending():
    """إيقاف الإرسال"""
    global is_running, client
    
    try:
        is_running = False
        update_status("متوقف")
        log_message("⏹️ تم إيقاف النظام")
        
        if client:
            try:
                asyncio.create_task(client.disconnect())
            except:
                pass
                
        return jsonify({"success": True, "message": "تم إيقاف النظام"})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/test_send', methods=['POST'])
def test_send():
    """إرسال تجريبي"""
    global client, current_settings
    
    try:
        if not client:
            return jsonify({"success": False, "error": "يجب تسجيل الدخول أولاً"})
        
        current_settings = request.get_json()
        
        # إرسال للمجموعة الأولى فقط
        test_group = "Maths_genius2"
        
        thread = threading.Thread(target=send_test_message, args=(test_group,), daemon=True)
        thread.start()
        
        return jsonify({"success": True, "message": "جاري الإرسال التجريبي..."})
        
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

def send_test_message(group):
    """إرسال رسالة تجريبية"""
    async def _send():
        try:
            message = current_settings.get('message', '')
            await client.send_message(group, message, parse_mode='markdown')
            log_message(f"✅ تم إرسال رسالة تجريبية إلى {group}")
        except Exception as e:
            log_message(f"❌ فشل الإرسال التجريبي: {str(e)}")
    
    asyncio.run(_send())

def run_telegram_client():
    """تشغيل عميل تيليجرام"""
    asyncio.run(telegram_main())

async def telegram_main():
    """الدالة الرئيسية لتيليجرام"""
    global client
    
    try:
        # إنشاء مجلد الجلسات
        if not os.path.exists("sessions"):
            os.makedirs("sessions")
            
        phone = current_settings['phone']
        api_id = int(current_settings['api_id'])
        api_hash = current_settings['api_hash']
        code = current_settings['code']
        password = current_settings.get('password', '')
        
        session_name = f"sessions/{phone.replace('+', '')}"
        client = TelegramClient(session_name, api_id, api_hash)
        
        log_message("🔹 جاري الاتصال بتيليجرام...")
        await client.connect()
        
        if not await client.is_user_authorized():
            await client.send_code_request(phone)
            log_message("🔹 تم إرسال كود التحقق")
            
            try:
                await client.sign_in(phone, code)
            except Exception as e:
                if "password" in str(e).lower() and password:
                    await client.sign_in(password=password)
                else:
                    log_message(f"❌ خطأ في التحقق: {str(e)}")
                    return
                    
        log_message("✅ تم تسجيل الدخول بنجاح!")
        
        # بدء الإرسال المستمر
        await continuous_sending()
        
    except Exception as e:
        log_message(f"❌ خطأ في النظام: {str(e)}")
    finally:
        if client:
            await client.disconnect()

async def continuous_sending():
    """الإرسال المستمر للرسائل"""
    global is_running
    
    while is_running:
        try:
            message = current_settings.get('message', '')
            log_message(f"🚀 بدء البث إلى {len(GROUPS)} مجموعة...")
            
            success_count = 0
            for group in GROUPS:
                if not is_running:
                    break
                    
                try:
                    await client.send_message(group, message, parse_mode='markdown')
                    log_message(f"✅ {group}")
                    success_count += 1
                except Exception as e:
                    log_message(f"❌ {group}: {str(e)[:50]}...")
                    
                await asyncio.sleep(2)
                
            log_message(f"📊 انتهى البث: {success_count}/{len(GROUPS)} رسالة")
            
            # انتظار الفاصل الزمني
            interval_minutes = int(current_settings.get('interval', 5))
            interval_seconds = interval_minutes * 60
            
            log_message(f"⏰ انتظار {interval_minutes} دقيقة...")
            await asyncio.sleep(interval_seconds)
            
        except Exception as e:
            log_message(f"❌ خطأ في الإرسال: {str(e)}")
            await asyncio.sleep(60)

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=False)