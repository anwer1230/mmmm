from flask import Flask, session, request, render_template_string
from flask_socketio import SocketIO, emit, join_room
from telethon import TelegramClient, events
import threading, asyncio, os, json, uuid

app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

SESSIONS_DIR = "sessions"
if not os.path.exists(SESSIONS_DIR):
    os.makedirs(SESSIONS_DIR)

USERS = {}

# ===========================
# حفظ واسترجاع الإعدادات
# ===========================
def save_settings(user_id, settings):
    path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, ensure_ascii=False, indent=4)

def load_settings(user_id):
    path = os.path.join(SESSIONS_DIR, f"{user_id}.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

# ===========================
# مهمة المراقبة لكل مستخدم
# ===========================
def monitoring_task(user_id):
    user_data = USERS[user_id]
    client = user_data['client']
    settings = user_data['settings']

    async def async_monitor():
        @client.on(events.NewMessage)
        async def handler(event):
            msg = event.message.message
            for word in settings.get("watch_words", []):
                if word in msg:
                    await client.send_message('me', f"🔔 رصدت كلمة: {word}")
                    socketio.emit('log_update', {"message": f"🔔 رصدت كلمة: {word}"}, room=user_id)
            socketio.emit('log_update', {"message": f"📩 {event.chat_id}: {msg}"}, room=user_id)

        await client.start(phone=settings['phone'], password=settings.get('password'))
        socketio.emit('log_update', {"message": "✅ تم تسجيل الدخول"}, room=user_id)

        while user_data['is_running']:
            if settings.get("send_type") == "automatic":
                for group in settings.get("groups", []):
                    try:
                        await client.send_message(group, settings.get("message",""))
                        socketio.emit('log_update', {"message": f"🚀 أرسلت رسالة إلى {group}"}, room=user_id)
                    except Exception as e:
                        socketio.emit('log_update', {"message": f"❌ {group}: {str(e)}"}, room=user_id)
            await asyncio.sleep(int(settings.get("interval_seconds", 60)))

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(async_monitor())

# ===========================
# الراوتات
# ===========================
@app.route("/")
def index():
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_id = session['user_id']
    return render_template_string(INDEX_HTML, user_id=user_id)

@app.route("/api/save_settings", methods=["POST"])
def api_save_settings():
    user_id = session['user_id']
    settings = request.json
    save_settings(user_id, settings)
    try:
        client = TelegramClient(
            os.path.join(SESSIONS_DIR, user_id),
            int(settings['api_id']),
            settings['api_hash']
        )
        USERS[user_id] = {
            'client': client,
            'settings': settings,
            'thread': None,
            'is_running': False
        }
        return {"success": True, "message": "✅ تم حفظ البيانات"}
    except Exception as e:
        return {"success": False, "message": f"❌ خطأ: {str(e)}"}

@app.route("/api/start_monitoring", methods=["POST"])
def api_start_monitoring():
    user_id = session['user_id']
    if user_id not in USERS:
        return {"success": False, "message": "❌ لم تحفظ البيانات بعد"}
    user_data = USERS[user_id]
    if user_data['is_running']:
        return {"success": False, "message": "❌ النظام يعمل بالفعل"}
    user_data['is_running'] = True
    thread = threading.Thread(target=monitoring_task, args=(user_id,))
    thread.start()
    user_data['thread'] = thread
    return {"success": True, "message": "🚀 بدأت المراقبة"}

@app.route("/api/stop_monitoring", methods=["POST"])
def api_stop_monitoring():
    user_id = session['user_id']
    if user_id in USERS:
        USERS[user_id]['is_running'] = False
        return {"success": True, "message": "⏹ تم إيقاف المراقبة"}
    return {"success": False, "message": "❌ لم يتم تشغيل النظام"}

@app.route("/api/send_now", methods=["POST"])
def api_send_now():
    user_id = session['user_id']
    if user_id not in USERS:
        return {"success": False, "message": "❌ لم تحفظ البيانات بعد"}
    settings = USERS[user_id]['settings']
    client = USERS[user_id]['client']

    async def send_all():
        await client.start(phone=settings['phone'], password=settings.get('password'))
        for group in settings.get("groups", []):
            try:
                await client.send_message(group, settings.get("message",""))
                socketio.emit('log_update', {"message": f"🚀 أرسلت رسالة إلى {group}"}, room=user_id)
            except Exception as e:
                socketio.emit('log_update', {"message": f"❌ {group}: {str(e)}"}, room=user_id)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(send_all())
    return {"success": True, "message": "✅ تم إرسال الرسائل فوري"}

# ===========================
# SocketIO
# ===========================
@socketio.on('join')
def on_join(data):
    join_room(session['user_id'])

# ===========================
# واجهة HTML كاملة
# ===========================
INDEX_HTML = """<YOUR_HTML_HERE>"""  # ضع هنا واجهة HTML كما في كودك السابق

# ===========================
# تشغيل السيرفر
# ===========================
if __name__ == "__main__":
    import eventlet
    eventlet.monkey_patch()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
