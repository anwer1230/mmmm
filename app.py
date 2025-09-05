# app.py
from flask import Flask, request, session, redirect, url_for, render_template_string
from flask_socketio import SocketIO, emit, join_room, leave_room
from telethon import TelegramClient
import threading, time
import uuid
from itsdangerous import URLSafeSerializer

app = Flask(__name__)
app.secret_key = "S3cr3tKeyForSessions"  # لتشفير الجلسات
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# تشفير معرف الجلسة في الرابط
serializer = URLSafeSerializer(app.secret_key)

# تخزين بيانات كل مستخدم
user_sessions = {}  # { session_id: {settings, tg_client, thread, running} }

# -----------------------------
# HTML الموحد داخل التطبيق
# -----------------------------
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
.main-container { max-width: 1200px; margin: 20px auto; }
.card { box-shadow: 0 4px 6px rgba(0,0,0,0.1); border-radius: 10px; }
.card-header { background: linear-gradient(135deg,#667eea 0%,#764ba2 100%); color:white; border-radius:10px 10px 0 0 !important; }
.log-container { background-color: #000; color: #00ff00; font-family: monospace; height: 250px; overflow-y:auto; padding:10px; border-radius:5px; }
.btn-custom { border-radius: 25px; padding: 10px 30px; font-weight: bold; }
.form-control, .form-select { border-radius: 10px; }
textarea { resize: vertical; }
</style>
</head>
<body>
<div class="container-fluid main-container">
<div class="text-center mb-4">
<h1 class="display-4 text-primary"><i class="fas fa-robot"></i> نظام مراقبة وإرسال رسائل تيليجرام</h1>
<p class="lead text-muted">مركز سرعة إنجاز - النظام الآلي</p>
</div>
<div class="row">
<div class="col-lg-6">
<div class="card mb-4">
<div class="card-header"><h5><i class="fas fa-key"></i> بيانات الحساب</h5></div>
<div class="card-body">
<div class="row mb-3">
<div class="col-md-6"><label class="form-label">رقم الهاتف</label><input type="text" class="form-control" id="phone" placeholder="+966123456789"></div>
<div class="col-md-6"><label class="form-label">API ID</label><input type="text" class="form-control" id="api_id" placeholder="1234567"></div>
</div>
<div class="mb-3"><label class="form-label">API Hash</label><input type="text" class="form-control" id="api_hash" placeholder="abc123def456..."></div>
<div class="row mb-3">
<div class="col-md-6"><label class="form-label">كود التحقق</label><input type="text" class="form-control" id="code" placeholder="12345"></div>
<div class="col-md-6"><label class="form-label">كلمة المرور</label><input type="password" class="form-control" id="password" placeholder="إن وجدت"></div>
</div>
</div></div>
<div class="card mb-4">
<div class="card-header"><h5><i class="fas fa-cog"></i> إعدادات النظام</h5></div>
<div class="card-body">
<div class="mb-3">
<label class="form-label">المجموعات المستهدفة (افصل بين المجموعات بفاصلة)</label>
<input type="text" class="form-control" id="groups" placeholder="group1,group2,...">
</div>
<div class="mb-3">
<label class="form-label">مدة الإرسال / المراقبة (بالثواني)</label>
<input type="number" class="form-control" id="interval" value="5" min="1">
</div>
<div class="mb-3">
<label class="form-label">نوع الإرسال</label>
<select class="form-select" id="send_type">
<option value="immediate">فوري</option>
<option value="automatic">تلقائي</option>
</select>
</div>
<div class="mb-3">
<label class="form-label">كلمات المراقبة (افصل بفاصلة)</label>
<input type="text" class="form-control" id="keywords" placeholder="keyword1,keyword2,...">
</div>
</div></div>
<div class="card mb-4">
<div class="card-header"><h5><i class="fas fa-play-circle"></i> التحكم</h5></div>
<div class="card-body text-center">
<button class="btn btn-success btn-custom me-2" id="startBtn"><i class="fas fa-rocket"></i> بدء المراقبة</button>
<button class="btn btn-danger btn-custom me-2" id="stopBtn" disabled><i class="fas fa-stop"></i> إيقاف المراقبة</button>
<button class="btn btn-primary btn-custom me-2" id="saveBtn"><i class="fas fa-save"></i> حفظ الإعدادات</button>
<button class="btn btn-warning btn-custom" id="testBtn"><i class="fas fa-flask"></i> إرسال تجريبي</button>
</div></div></div>
<div class="col-lg-6">
<div class="card mb-4">
<div class="card-header"><h5><i class="fas fa-envelope"></i> نص الرسالة</h5></div>
<div class="card-body">
<textarea class="form-control" id="message" rows="10" placeholder="اكتب رسالتك هنا..."></textarea>
</div></div>
<div class="card">
<div class="card-header"><h5><i class="fas fa-list"></i> سجل العمليات والتنبيهات</h5></div>
<div class="card-body">
<div id="log" class="log-container"><div>[معلومات] مرحباً بك في النظام</div></div>
</div></div></div></div></div>
<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/js/bootstrap.bundle.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
<script>
const socket = io();
const elements = {
    phone: document.getElementById('phone'),
    api_id: document.getElementById('api_id'),
    api_hash: document.getElementById('api_hash'),
    code: document.getElementById('code'),
    password: document.getElementById('password'),
    groups: document.getElementById('groups'),
    message: document.getElementById('message'),
    interval: document.getElementById('interval'),
    send_type: document.getElementById('send_type'),
    keywords: document.getElementById('keywords'),
    startBtn: document.getElementById('startBtn'),
    stopBtn: document.getElementById('stopBtn'),
    saveBtn: document.getElementById('saveBtn'),
    testBtn: document.getElementById('testBtn'),
    log: document.getElementById('log')
};

function addLog(message){
    const div = document.createElement('div');
    div.textContent = message;
    elements.log.appendChild(div);
    elements.log.scrollTop = elements.log.scrollHeight;
}

// حفظ الإعدادات
elements.saveBtn.addEventListener('click', () => {
    fetch('/save_settings', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
            phone: elements.phone.value,
            api_id: elements.api_id.value,
            api_hash: elements.api_hash.value,
            code: elements.code.value,
            password: elements.password.value,
            groups: elements.groups.value,
            message: elements.message.value,
            interval: elements.interval.value,
            send_type: elements.send_type.value,
            keywords: elements.keywords.value
        })
    }).then(res=>res.json()).then(data=>{
addLog(data.success ? '✅ تم حفظ الإعدادات' : '❌ خطأ في الحفظ');
    });
});

// بدء المراقبة
elements.startBtn.addEventListener('click', ()=>{
    fetch('/start_monitoring',{method:'POST'}).then(res=>res.json()).then(data=>{
        if(data.success){
            addLog('🚀 بدء المراقبة');
            elements.startBtn.disabled = true;
            elements.stopBtn.disabled = false;
        } else addLog('❌ '+data.error);
    });
});

// إيقاف المراقبة
elements.stopBtn.addEventListener('click', ()=>{
    fetch('/stop_monitoring',{method:'POST'}).then(res=>res.json()).then(data=>{
        if(data.success){
            addLog('🛑 تم إيقاف المراقبة');
            elements.startBtn.disabled = false;
            elements.stopBtn.disabled = true;
        }
    });
});

// الاستماع للـ logs من السيرفر
socket.on('log_update', data=>{
    addLog(data.message);
});
</script>
</body>
</html>
"""

# -----------------------------
# وظائف Telegram
# -----------------------------
def init_telegram(settings):
    tg_client = TelegramClient(f"session_{settings['session_id']}", settings['api_id'], settings['api_hash'])
    tg_client.start(phone=settings['phone'], password=settings['password'], code_callback=lambda: settings['code'])
    return tg_client

def monitoring_thread_func(session_id):
    settings = user_sessions[session_id]['settings']
    tg_client = user_sessions[session_id]['tg_client']
    while user_sessions[session_id]['running']:
        groups = settings.get("groups", [])
        message = settings.get("message", "")
        watch_words = settings.get("watch_words", [])
        interval = int(settings.get("interval_seconds", 5))
        send_type = settings.get("send_type", "immediate")

        # إرسال الرسائل
        for group in groups:
            try:
                tg_client.send_message(group, message)
                socketio.emit('log_update', {"message": f"🚀 تم إرسال الرسالة إلى {group}"}, room=session_id)
            except Exception as e:
                socketio.emit('log_update', {"message": f"❌ {group}: {str(e)}"}, room=session_id)

        # إرسال التنبيهات الخاصة
        for word in watch_words:
            try:
                tg_client.send_message('me', f"🔔 تم رصد كلمة المراقبة: {word}")
                socketio.emit('log_update', {"message": f"🔔 تم إرسال التنبيه إلى حسابك الشخصي: {word}"}, room=session_id)
            except Exception as e:
                socketio.emit('log_update', {"message": f"❌ خطأ في إرسال التنبيه: {str(e)}"}, room=session_id)

        if send_type == "immediate":
            break
        time.sleep(interval)

# -----------------------------
# الراوتات
# -----------------------------
@app.route("/")
def index():
    if 'user_id' not in session:
        # إنشاء معرف مستخدم جديد لكل جلسة
        user_id = str(uuid.uuid4())
        session['user_id'] = user_id
        user_sessions[user_id] = {
            "settings": {"session_id": user_id},
            "tg_client": None,
            "thread": None,
            "running": False
        }
    return render_template_string(INDEX_HTML)

@app.route("/save_settings", methods=["POST"])
def save_settings_route():
    user_id = session['user_id']
    data = request.json
    # حفظ الإعدادات في الذاكرة فقط لكل مستخدم
    user_sessions[user_id]['settings'].update({
        "phone": data['phone'],
        "api_id": data['api_id'],
        "api_hash": data['api_hash'],
        "code": data['code'],
        "password": data['password'],
        "groups": [g.strip() for g in data['groups'].split(",") if g.strip()],
        "message": data['message'],
        "interval_seconds": int(data['interval']),
        "send_type": data['send_type'],
        "watch_words": [w.strip() for w in data['keywords'].split(",") if w.strip()]
    })
    return {"success": True}

@app.route("/start_monitoring", methods=["POST"])
def start_monitoring_route():
    user_id = session['user_id']
    user_data = user_sessions[user_id]
    if user_data['running']:
        return {"success": False, "error": "النظام يعمل بالفعل"}
    settings = user_data['settings']
    tg_client = init_telegram(settings)
    user_data['tg_client'] = tg_client
    user_data['running'] = True
    t = threading.Thread(target=monitoring_thread_func, args=(user_id,))
    t.start()
    user_data['thread'] = t
    return {"success": True}

@app.route("/stop_monitoring", methods=["POST"])
def stop_monitoring_route():
    user_id = session['user_id']
    user_sessions[user_id]['running'] = False
    return {"success": True}

# -----------------------------
# SocketIO: الانضمام للغرفة الخاصة بكل مستخدم
# -----------------------------
@socketio.on('connect')
def handle_connect():
    if 'user_id' in session:
        join_room(session['user_id'])

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        leave_room(session['user_id'])

# -----------------------------
# تشغيل التطبيق
# -----------------------------
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
