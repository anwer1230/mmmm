from flask import Flask, request, jsonify, send_from_directory
from flask_socketio import SocketIO
import eventlet
import threading
import time

eventlet.monkey_patch()

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

settings = {
    "phone": "",
    "api_id": "",
    "api_hash": "",
    "code": "",
    "password": "",
    "groups": "",
    "message": "",
    "interval": 5,
    "send_type": "auto",
    "keywords": []
}

sending_thread = None
monitoring = False

@app.route("/")
def index():
    return send_from_directory('.', 'index.html')

@app.route("/api/load_settings", methods=["GET"])
def load_settings():
    return jsonify({"success": True, "settings": settings})

@app.route("/api/save_settings", methods=["POST"])
def save_settings():
    global settings
    data = request.json
    settings.update(data)
    socketio.emit('log_update', {"message": "✅ تم حفظ الإعدادات بنجاح"})
    return jsonify({"success": True})

@app.route("/api/start_sending", methods=["POST"])
def start_sending():
    global sending_thread, monitoring
    if sending_thread and sending_thread.is_alive():
        return jsonify({"success": False, "error": "النظام يعمل بالفعل"})
    
    monitoring = True
    sending_thread = threading.Thread(target=send_loop)
    sending_thread.start()
    socketio.emit('status_update', {"status": "يعمل"})
    socketio.emit('log_update', {"message": "🚀 بدء المراقبة والإرسال..."})
    return jsonify({"success": True})

@app.route("/api/stop_sending", methods=["POST"])
def stop_sending():
    global monitoring
    monitoring = False
    socketio.emit('status_update', {"status": "متوقف"})
    socketio.emit('log_update', {"message": "⏹ تم إيقاف النظام"})
    return jsonify({"success": True})

def send_loop():
    while monitoring:
        groups = settings.get("groups", "").split(",")
        message = settings.get("message", "")
        for group in groups:
            group = group.strip()
            if not group:
                continue
            # هنا تضع كود إرسال الرسالة عبر تيليجرام
            socketio.emit('log_update', {"message": f"📩 تم إرسال الرسالة إلى {group}"})
            time.sleep(0.5)

        keywords = [k.strip() for k in settings.get("keywords", []) if k.strip()]
        if keywords:
            for kw in keywords:
                socketio.emit('log_update', {"message": f"🔍 تم رصد الكلمة: {kw}"})

        interval = int(settings.get("interval", 5))
        time.sleep(interval)

@socketio.on('connect')
def handle_connect():
    socketio.emit('log_update', {"message": "✅ تم الاتصال بالواجهة بنجاح"})

if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
