# ===========================
# استيراد المكتبات
# ===========================
import os, json, uuid, threading
from flask import Flask, session, request, render_template_string
from flask_socketio import SocketIO, emit, join_room
import asyncio

# ======= تفعيل eventlet قبل أي استيراد آخر =======
import eventlet
eventlet.monkey_patch()

from telethon import TelegramClient, events

# ===========================
# إعداد Flask و SocketIO
# ===========================
app = Flask(__name__)
app.secret_key = os.urandom(24)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# ===========================
# إعداد الملفات والمستخدمين
# ===========================
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
INDEX_HTML = """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>نظام مراقبة وإرسال رسائل تيليجرام</title>
<link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
<link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.0.0/css/all.min.css" rel="stylesheet">
<style>
body { font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #f8f9fa; }
.card { border-radius:10px; box-shadow:0 4px 6px rgba(0,0,0,0.1);}
.card-header { background: linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; border-radius:10px 10px 0 0 !important;}
.log-container { background-color:#000; color:#0f0; font-family: monospace; height:200px; overflow-y:auto; padding:10px; border-radius:5px;}
.btn-custom { border-radius:25px; padding:10px 30px; font-weight:bold;}
.form-control { border-radius:10px; }
</style>
</head>
<body>
<div class="container mt-3">
    <div class="card p-3">
        <h4>تسجيل الدخول</h4>
        <input class="form-control mb-2" id="phone" placeholder="رقم الهاتف">
        <input class="form-control mb-2" id="api_id" placeholder="API ID">
        <input class="form-control mb-2" id="api_hash" placeholder="API Hash">
        <input class="form-control mb-2" id="password" placeholder="كلمة المرور (إن وجدت)">
        <button class="btn btn-primary btn-custom mb-2" id="loginBtn">موافق</button>
    </div>
    <div class="card p-3 mt-3">
        <h4>إعدادات النظام</h4>
        <textarea class="form-control mb-2" id="message" placeholder="نص الرسالة"></textarea>
        <textarea class="form-control mb-2" id="groups" placeholder="روابط المجموعات (افصل بينهم بفواصل)"></textarea>
        <input class="form-control mb-2" id="interval" type="number" value="60" placeholder="الفترة الزمنية">
        <input class="form-control mb-2" id="keywords" placeholder="كلمات المراقبة (افصل بينهم بفواصل)">
        <button class="btn btn-primary btn-custom mb-2" id="saveBtn">حفظ البيانات</button>
        <button class="btn btn-success btn-custom mb-2" id="sendNowBtn">إرسال فوري</button>
        <button class="btn btn-info btn-custom mb-2" id="sendAutoBtn">إرسال تلقائي</button>
        <button class="btn btn-warning btn-custom mb-2" id="startBtn">بدء المراقبة</button>
        <button class="btn btn-danger btn-custom mb-2" id="stopBtn">إيقاف المراقبة</button>
    </div>
    <div class="card p-3 mt-3">
        <h4>سجل العمليات</h4>
        <div id="log" class="log-container"></div>
    </div>
</div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
const socket = io();
socket.emit('join',{});
function addLog(msg){const l=document.getElementById('log');l.innerHTML+='<div>'+msg+'</div>';l.scrollTop=l.scrollHeight;}

// حفظ البيانات
document.getElementById('saveBtn').onclick = ()=>{
    fetch('/api/save_settings',{
        method:'POST', headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
            phone: document.getElementById('phone').value,
            api_id: document.getElementById('api_id').value,
            api_hash: document.getElementById('api_hash').value,
            password: document.getElementById('password').value,
            message: document.getElementById('message').value,
            groups: document.getElementById('groups').value.split(','),
            interval_seconds: document.getElementById('interval').value,
            send_type: 'automatic',
            watch_words: document.getElementById('keywords').value.split(',')
        })
}).then(r=>r.json()).then(d=>addLog(d.message))
}

// بدء المراقبة
document.getElementById('startBtn').onclick = ()=>{
    fetch('/api/start_monitoring',{method:'POST'}).then(r=>r.json()).then(d=>addLog(d.message))
}

// إيقاف المراقبة
document.getElementById('stopBtn').onclick = ()=>{
    fetch('/api/stop_monitoring',{method:'POST'}).then(r=>r.json()).then(d=>addLog(d.message))
}

// إرسال فوري
document.getElementById('sendNowBtn').onclick = ()=>{
    fetch('/api/send_now',{method:'POST'}).then(r=>r.json()).then(d=>addLog(d.message))
}

// تحديث السجل من السيرفر
socket.on('log_update', data => addLog(data.message))
</script>
</body>
</html>
"""

# ===========================
# تشغيل السيرفر
# ===========================
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
