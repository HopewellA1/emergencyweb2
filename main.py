from flask import Flask, render_template
from flask_socketio import SocketIO
import threading
import firebase_admin
from firebase_admin import credentials, firestore
import json
import os
from dotenv import load_dotenv


load_dotenv()
cred = credentials.Certificate({
    "type": os.getenv("FIREBASE_TYPE"),
    "project_id": os.getenv("FIREBASE_PROJECT_ID"),
    "private_key_id": os.getenv("FIREBASE_PRIVATE_KEY_ID"),
    "private_key": os.getenv("FIREBASE_PRIVATE_KEY").replace('\\n', '\n'),
    "client_email": os.getenv("FIREBASE_CLIENT_EMAIL"),
    "client_id": os.getenv("FIREBASE_CLIENT_ID"),
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token",
    "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
    "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/firebase-adminsdk-fbsvc%40{os.getenv('FIREBASE_PROJECT_ID')}.iam.gserviceaccount.com"
})

firebase_admin.initialize_app(cred)
import eventlet
eventlet.monkey_patch()
app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key'
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')
# Firebase connection

db = firestore.client()

def serialize_firestore(obj):
    if hasattr(obj, 'isoformat'):          # datetime
        return obj.isoformat()
    if hasattr(obj, 'latitude'):           # GeoPoint
        return {'lat': obj.latitude, 'lng': obj.longitude}
    if isinstance(obj, dict):
        return {k: serialize_firestore(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [serialize_firestore(i) for i in obj]
    return obj

def watch_incidents():
    def on_snapshot(col_snapshot, changes, read_time):
        data = [serialize_firestore(doc.to_dict() | {'id': doc.id}) for doc in col_snapshot]
        socketio.emit('incidents_update', data)
    db.collection('incidents').on_snapshot(on_snapshot)

@app.route("/")
def home():
    return render_template('main/home.html')


def countObj(li):
    num = 0
    for i in li:
        num += 1
    return num


@app.route("/dashboard")
def dashboard():
    incidents_data = []
    for doc in db.collection('incidents').stream():
        d = doc.to_dict()
        d['id'] = doc.id
        incidents_data.append(serialize_firestore(d))


    print("incidents_data: ", incidents_data)
    users_data = []
    for doc in db.collection('users').stream():
        d = doc.to_dict()
        d['id'] = doc.id
        users_data.append(serialize_firestore(d))

    return render_template(
        'main/admin-dashboard.html',
        incidents=incidents_data,
        users=users_data,
        incidents_json=json.dumps(incidents_data),
        users_json=json.dumps(users_data),
        Open  = countObj(filter_incidents(incidents_data, "open")),
        inProgress  = countObj(filter_incidents(incidents_data, "inProgress")),
        resolved  = countObj(filter_incidents(incidents_data, "resolved")),
        closed  = countObj(filter_incidents(incidents_data, "closed")),
       
    )




def filter_incidents(incidents, status=None, priority=None, min_risk=None, unassigned_only=False):
    """
    Filter incidents by any combination of:
    - status         : 'open', 'inProgress', 'resolved', 'closed'
    - priority       : 'critical', 'high', 'medium', 'low'
    - min_risk       : minimum riskScore (1-5)
    - unassigned_only: only incidents with no responder assigned
    """
    result = incidents

    if status:
        result = [i for i in result if i.get('status') == status]

    if priority:
        result = [i for i in result if i.get('priority') == priority]

    if min_risk is not None:
        result = [i for i in result if i.get('riskScore', 0) >= min_risk]

    if unassigned_only:
        result = [i for i in result if i.get('assignedResponder') is None]

    return result


# # ── Usage examples ────────────────────────────────────────────
# open_incidents    = filter_incidents(incidents, status='open')
# critical          = filter_incidents(incidents, priority='critical')
# high_risk         = filter_incidents(incidents, min_risk=4)
# urgent_unassigned = filter_incidents(incidents, status='open', priority='critical', unassigned_only=True)
# in_progress       = filter_incidents(incidents, status='inProgress')
# if __name__ == "__main__":
#     threading.Thread(target=watch_incidents, daemon=True).start()
#     socketio.run(app, host='127.0.0.1', port=5000, debug=False)


if __name__ == "__main__":
    threading.Thread(target=watch_incidents, daemon=True).start()
    socketio.run(app, host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), allow_unsafe_werkzeug=True, debug=False)
    
