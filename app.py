from flask import Flask, request, send_file, jsonify
from flask_socketio import SocketIO, emit
from telethon import TelegramClient
import threading
import time
import json
import os

# -----------------------------
# بيانات التطبيق
# -----------------------------
app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')
SETTINGS_FILE = "settings.json"

is_running = False
monitoring_thread = None
tg_client = None

# -----------------------------
# وظائف التحميل والحفظ
# -----------------------------
def load_settings():
    if os.path.exists(SETTINGS_FILE):
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_settings(settings):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

# -----------------------------
# إعداد تيليجرام
# -----------------------------
def init_telegram(settings):
    global tg_client
    if tg_client is None:
        tg_client = TelegramClient(
            'session', 
            settings['api_id'], 
            settings['api_hash']
        )
        tg_client.start(phone=settings['phone'], password=settings['password'], code_callback=lambda: settings['code'])

# -----------------------------
# وظيفة المراقبة/الإرسال
# -----------------------------
def start_monitoring(settings):
    global is_running
    init_telegram(settings)

    while is_running:
        groups = settings.get("groups", [])
        message = settings.get("message", "")
        watch_words = settings.get("watch_words", [])
        interval = int(settings.get("interval_seconds", 5))

        # إرسال الرسائل إلى المجموعات
        for group in groups:
            try:
                tg_client.send_message(group, message)
                socketio.emit('log_update', {"message": f"🚀 تم إرسال الرسالة إلى {group}"})
            except Exception as e:
                socketio.emit('log_update', {"message": f"❌ {group}: {str(e)}"})
        
        # إرسال التنبيهات الخاصة إلى الحساب نفسه
        for word in watch_words:
            try:
                tg_client.send_message('me', f"🔔 تم رصد كلمة المراقبة: {word}")
                socketio.emit('log_update', {"message": f"🔔 تم إرسال التنبيه إلى حسابك الشخصي: {word}"})
            except Exception as e:
                socketio.emit('log_update', {"message": f"❌ خطأ في إرسال التنبيه: {str(e)}"})

        time.sleep(interval)

# -----------------------------
# الراوتات
# -----------------------------
@app.route("/")
def index():
    return send_file("index.html")

@app.route("/api/load_settings")
def api_load_settings():
    settings = load_settings()
    return jsonify({"success": True, "settings": settings})

@app.route("/api/save_settings", methods=["POST"])
def api_save_settings():
    data = request.json
    save_settings(data)
    return jsonify({"success": True})

@app.route("/api/start_monitoring", methods=["POST"])
def api_start_monitoring():
    global is_running, monitoring_thread
    if is_running:
        return jsonify({"success": False, "error": "النظام يعمل بالفعل"})
    settings = request.json
    save_settings(settings)
    is_running = True
    monitoring_thread = threading.Thread(target=start_monitoring, args=(settings,))
    monitoring_thread.start()
    return jsonify({"success": True})

@app.route("/api/stop_monitoring", methods=["POST"])
def api_stop_monitoring():
    global is_running
    is_running = False
    return jsonify({"success": True})

# -----------------------------
# تشغيل التطبيق
# -----------------------------
if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000)
