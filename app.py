from flask import Flask, request, jsonify, send_file
from flask_socketio import SocketIO, emit
from telethon import TelegramClient, events
import threading
import time
import json

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")

# إعدادات افتراضية
settings = {
    "phone": "",
    "api_id": 0,
    "api_hash": "",
    "code": "",
    "password": "",
    "groups": [],
    "message": "",
    "interval": 5,
    "send_type": "immediate",
    "keywords": []
}

client = None
monitor_thread = None
monitoring = False

@app.route('/api/save_settings', methods=['POST'])
def save_settings():
    global settings
    try:
        data = request.get_json()
        settings.update(data)
        settings['groups'] = [g.strip() for g in settings['groups'].split(',') if g.strip()]
        settings['keywords'] = [k.strip() for k in settings['keywords'].split(',') if k.strip()]
        with open('settings.json','w',encoding='utf-8') as f:
            json.dump(settings, f, ensure_ascii=False, indent=4)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/start_monitor', methods=['POST'])
def start_monitor():
    global client, monitor_thread, monitoring
    if monitoring:
        return jsonify({"success": False, "error": "المراقبة تعمل بالفعل"})
    try:
        monitoring = True
        monitor_thread = threading.Thread(target=run_monitor)
        monitor_thread.start()
        return jsonify({"success": True})
    except Exception as e:
        monitoring = False
        return jsonify({"success": False, "error": str(e)})

@app.route('/api/stop_monitor', methods=['POST'])
def stop_monitor():
    global monitoring
    monitoring = False
    return jsonify({"success": True})

# إرسال ملف الواجهة من نفس المجلد
@app.route('/')
def index():
    return send_file('index.html')

def run_monitor():
    global client, monitoring
    try:
        client = TelegramClient(settings['phone'], settings['api_id'], settings['api_hash'])
        client.connect()
        if not client.is_user_authorized():
            client.send_code_request(settings['phone'])
            client.sign_in(settings['phone'], settings['code'], password=settings['password'])
        socketio.emit('log_update', {'message': '✅ تم تسجيل الدخول بنجاح!'})
        
        @client.on(events.NewMessage)
        async def handler(event):
            if not monitoring:
                return
            text = event.message.message
            for keyword in settings['keywords']:
                if keyword in text:
                    socketio.emit('notification', {'message': f'كلمة مراقبة: "{keyword}" من {event.chat_id}'})
        
        client.start()
        socketio.emit('log_update', {'message': f'🚀 بدء المراقبة والإرسال...'})
        
        while monitoring:
            if settings['send_type'] == 'automatic' and settings['message']:
                for group in settings['groups']:
                    try:
                        client.send_message(group, settings['message'])
                        socketio.emit('log_update', {'message': f'✅ تم الإرسال إلى {group}'})
                    except Exception as e:
                        socketio.emit('log_update', {'message': f'❌ {group}: {str(e)}'})
            time.sleep(int(settings['interval']))
        
    except Exception as e:
        socketio.emit('log_update', {'message': f'❌ خطأ: {str(e)}'})
    finally:
        if client:
            client.disconnect()
        monitoring = False
        socketio.emit('log_update', {'message': '🛑 تم إيقاف المراقبة'})

if __name__ == '__main__':
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)
