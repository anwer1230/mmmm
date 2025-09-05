# app.py (ملف واحد: الواجهة + الخلفية)
from flask import Flask, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from telethon import TelegramClient
import threading
import time
import uuid

# -----------------------------
# بيانات التطبيق
# -----------------------------
app = Flask(__name__)
app.secret_key = "YOUR_SECRET_KEY_HERE"  # لتخزين جلسة المستخدم
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='gevent')

# تخزين الجلسات: كل مستخدم له مفتاح فريد
user_sessions = {}

# -----------------------------
# وظائف Telegram
# -----------------------------
def init_telegram(user_id, settings):
    client = TelegramClient(f"sessions/{user_id}", settings['api_id'], settings['api_hash'])
    return client

def start_monitoring(user_id):
    settings = user_sessions[user_id]['settings']
    client = user_sessions[user_id]['tg_client']
    interval = int(settings.get("interval_seconds", 5))
    groups = settings.get("groups", [])
    message = settings.get("message", "")
    watch_words = settings.get("watch_words", [])

    while user_sessions[user_id]['running']:
        # إرسال الرسائل إلى المجموعات
        for group in groups:
            try:
                client.send_message(group, message)
                socketio.emit('log_update', {"message": f"🚀 تم إرسال الرسالة إلى {group}"}, room=user_id)
            except Exception as e:
                socketio.emit('log_update', {"message": f"❌ {group}: {str(e)}"}, room=user_id)

        # إرسال التنبيهات إلى الحساب نفسه
        for word in watch_words:
            try:
                client.send_message('me', f"🔔 تم رصد كلمة المراقبة: {word}")
                socketio.emit('log_update', {"message": f"🔔 تم إرسال التنبيه إلى حسابك الشخصي: {word}"}, room=user_id)
            except Exception as e:
                socketio.emit('log_update', {"message": f"❌ خطأ في إرسال التنبيه: {str(e)}"}, room=user_id)

        time.sleep(interval)

# -----------------------------
# الراوتات
# -----------------------------
@app.route("/")
def index():
    # إنشاء معرف جلسة فريد لكل مستخدم
    if 'user_id' not in session:
        session['user_id'] = str(uuid.uuid4())
    user_id = session['user_id']
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            'settings': {},
            'tg_client': None,
            'running': False,
            'thread': None
        }
    return """
<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head>
<meta charset="UTF-8">
<title>نظام مراقبة تيليجرام</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
</head>
<body>
<h2>نظام مراقبة وإرسال رسائل تيليجرام</h2>

<div>
    <label>رقم الهاتف:</label><input id="phone"><br>
    <label>API ID:</label><input id="api_id"><br>
    <label>API Hash:</label><input id="api_hash"><br>
    <label>كلمة المرور (إن وجدت):</label><input id="password"><br>
    <button onclick="saveSettings()">حفظ البيانات</button>
</div>

<div>
    <label>كود التحقق:</label><input id="code">
    <button onclick="startLogin()">موافق</button>
</div>

<div>
    <label>المجموعات:</label><input id="groups" placeholder="group1,group2"><br>
    <label>كلمات المراقبة:</label><input id="watch_words" placeholder="كلمة1,كلمة2"><br>
    <label>نص الرسالة:</label><textarea id="message"></textarea><br>
    <label>مدة الإرسال/المراقبة بالثواني:</label><input id="interval" value="5"><br>
    <label>نوع الإرسال:</label>
    <select id="send_type">
        <option value="immediate">فوري</option>
        <option value="automatic">تلقائي</option>
    </select>
    <br>
    <button onclick="startMonitor()">بدء المراقبة</button>
    <button onclick="stopMonitor()">إيقاف المراقبة</button>
</div>

<h3>سجل العمليات:</h3>
<div id="log" style="border:1px solid #000; height:200px; overflow:auto;"></div>

<script>
var socket = io();
var user_id = "";

socket.on('connect', function(){
    console.log("متصل بالويب سوكت");
});

socket.on('session_id', function(data){
    user_id = data.user_id;
});

socket.on('log_update', function(data){
    var log = document.getElementById('log');
    log.innerHTML += "<div>"+data.message+"</div>";
    log.scrollTop = log.scrollHeight;
});

function saveSettings(){
    fetch('/save_settings', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
            phone: document.getElementById('phone').value,
            api_id: document.getElementById('api_id').value,
            api_hash: document.getElementById('api_hash').value,
            password: document.getElementById('password').value
        })
    }).then(res=>res.json()).then(data=>{
        document.getElementById('log').innerHTML += "<div>"+data.message+"</div>";
    });
}

function startLogin(){
    fetch('/start_login', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({code: document.getElementById('code').value})
    }).then(res=>res.json()).then(data=>{
        document.getElementById('log').innerHTML += "<div>"+data.message+"</div>";
    });
}

function startMonitor(){
    fetch('/start_monitor', {
        method:'POST',
        headers:{'Content-Type':'application/json'},
        body: JSON.stringify({
            groups: document.getElementById('groups').value.split(','),
            watch_words: document.getElementById('watch_words').value.split(','),
            message: document.getElementById('message').value,
            interval_seconds: document.getElementById('interval').value,
            send_type: document.getElementById('send_type').value
        })
    }).then(res=>res.json()).then(data=>{
        document.getElementById('log').innerHTML += "<div>"+data.message+"</div>";
    });
}

function stopMonitor(){
    fetch('/stop_monitor', {method:'POST'}).then(res=>res.json()).then(data=>{
        document.getElementById('log').innerHTML += "<div>"+data.message+"</div>";
    });
}
</script>
</body>
</html>
"""

# -----------------------------
# API الخلفية
# -----------------------------
@app.route("/save_settings", methods=["POST"])
def save_settings_route():
    user_id = session['user_id']
    settings = request.json
    user_sessions[user_id]['settings'] = settings
    return {"success": True, "message": "✅ تم حفظ البيانات"}

@app.route("/start_login", methods=["POST"])
def start_login():
    user_id = session['user_id']
    code = request.json.get('code')
    settings = user_sessions[user_id]['settings']
    try:
        client = init_telegram(user_id, settings)
        client.sign_in(code=code)
        user_sessions[user_id]['tg_client'] = client
        return {"success": True, "message": "✅ تم تسجيل الدخول بنجاح"}
    except Exception as e:
        return {"success": False, "message": f"❌ خطأ تسجيل الدخول: {str(e)}"}

@app.route("/start_monitor", methods=["POST"])
def start_monitor():
    user_id = session['user_id']
    settings = request.json
    user_sessions[user_id]['settings'].update(settings)
    if user_sessions[user_id]['running']:
        return {"success": False, "message": "النظام يعمل بالفعل"}
    user_sessions[user_id]['running'] = True
    thread = threading.Thread(target=start_monitoring, args=(user_id,))
    user_sessions[user_id]['thread'] = thread
    thread.start()
    return {"success": True, "message": "🚀 بدأت المراقبة"}

@app.route("/stop_monitor", methods=["POST"])
def stop_monitor():
    user_id = session['user_id']
    user_sessions[user_id]['running'] = False
    return {"success": True, "message": "🛑 تم إيقاف المراقبة"}

# -----------------------------
# تشغيل التطبيق
# -----------------------------
if __name__ == "__main__":
    socketio.run(app, host='0.0.0.0', port=5000, debug=True, allow_unsafe_werkzeug=True)
