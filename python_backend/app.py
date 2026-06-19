import os
import cv2
import random
import socket
import qrcode
from io import BytesIO
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)

# Indices used for “body present” scoring (nose, shoulders, hips, ankles).
_CORE_POSE_INDICES = (0, 11, 12, 23, 24, 27, 28)


def _score_human_from_landmarks(lms):
    """Return (human_probability 0..1, strong_core_count, avg_core_vis, human_detected)."""
    if not lms or len(lms) < 33:
        return 0.0, 0, 0.0, False
    vis_all = [float(lms[i].visibility) for i in range(33)]
    avg_all = sum(vis_all) / 33.0
    core_vis = [float(lms[i].visibility) for i in _CORE_POSE_INDICES]
    avg_core = sum(core_vis) / len(core_vis)
    strong = sum(1 for v in core_vis if v >= 0.4)
    prob = min(
        1.0,
        0.25 * avg_all + 0.45 * avg_core + 0.30 * (strong / len(_CORE_POSE_INDICES)),
    )
    detected = prob >= 0.42 and strong >= 4
    return prob, strong, avg_core, detected


def _corsify(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    return resp


def get_local_ip():
    try:
        # Create a dummy socket to connect to an external IP
        # This will route through the default interface and return its IP
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

@app.route('/')
def index():
    # request.host_url dynamically adapts to ngrok/localtunnel or local IP
    display_url = request.host_url.rstrip('/')
    return render_template('index.html', display_url=display_url)

@app.route('/qr')
def generate_qr():
    url = request.host_url
    
    img = qrcode.make(url)
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')

    response.headers.add('Access-Control-Allow-Headers', 'Content-Type,Authorization')
    response.headers.add('Access-Control-Allow-Methods', 'GET,PUT,POST,DELETE,OPTIONS')
    return response

# Captured photos (served back to the client after upload)
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'images')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER


@app.route('/captured/<filename>')
def serve_captured(filename):
    safe = secure_filename(filename)
    if not safe or safe != filename or filename.startswith('.'):
        return jsonify({'error': 'Invalid filename'}), 400
    path = os.path.join(UPLOAD_FOLDER, safe)
    if not os.path.isfile(path):
        return jsonify({'error': 'Not found'}), 404
    return send_from_directory(UPLOAD_FOLDER, safe)

# Try to initialize MediaPipe Pose (Fails on Python 3.13 often due to missing 'solutions')
try:
    import mediapipe as mp
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=True,
        model_complexity=1,
        min_detection_confidence=0.5
    )
    HAS_MEDIAPIPE = True
    print("MediaPipe successfully initialized")
except (ImportError, AttributeError) as e:
    print(f"Warning: Could not initialize MediaPipe fully ({e}). Using mock detection fallback.")
    HAS_MEDIAPIPE = False

@app.route("/analyze", methods=["OPTIONS"])
def analyze_image_options():
    return _corsify(app.make_response("", 204))


@app.route('/analyze', methods=['POST'])
def analyze_image():
    if 'image' not in request.files:
        r = jsonify({'error': 'No image part in the request'})
        return _corsify(r), 400

    file = request.files['image']

    if file.filename == '':
        r = jsonify({'error': 'No selected file'})
        return _corsify(r), 400

    filename = secure_filename(file.filename)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    name, ext = os.path.splitext(filename)
    unique_filename = f"{name}_{timestamp}{ext}"
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)

    file.save(filepath)

    image = cv2.imread(filepath)
    if image is None:
        r = jsonify({'error': 'Failed to read the image file'})
        return _corsify(r), 400

    landmarks_data = []
    human_detected = False
    human_probability = 0.0
    strong_core = 0
    avg_core_visibility = 0.0
    avg_all_visibility = 0.0

    if HAS_MEDIAPIPE:
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        results = pose.process(image_rgb)

        if results.pose_landmarks:
            lms = list(results.pose_landmarks.landmark)
            human_probability, strong_core, avg_core_visibility, human_detected = (
                _score_human_from_landmarks(lms)
            )
            avg_all_visibility = sum(float(x.visibility) for x in lms) / max(len(lms), 1)

            for idx, landmark in enumerate(lms):
                landmarks_data.append({
                    'id': idx,
                    'name': mp_pose.PoseLandmark(idx).name,
                    'x': landmark.x,
                    'y': landmark.y,
                    'z': landmark.z,
                    'visibility': landmark.visibility
                })
        else:
            human_probability = 0.0
            human_detected = False
    else:
        # MOCK IMPLEMENTATION FOR PYTHON 3.13 COMPATIBILITY
        human_probability = round(random.uniform(0.15, 0.95), 3)
        human_detected = human_probability >= 0.5
        strong_core = random.randint(3, 7) if human_detected else random.randint(0, 2)
        avg_core_visibility = min(
            1.0, human_probability * 0.9 + random.uniform(-0.05, 0.05)
        )
        avg_all_visibility = min(1.0, human_probability * 0.85)
        if human_detected:
            for idx in range(33):
                landmarks_data.append({
                    'id': idx,
                    'name': f"MOCK_LANDMARK_{idx}",
                    'x': random.uniform(0.1, 0.9),
                    'y': random.uniform(0.1, 0.9),
                    'z': random.uniform(-0.5, 0.5),
                    'visibility': random.uniform(0.75, 1.0)
                })

    payload = {
        'message': 'Image successfully processed (Mock Mode)' if not HAS_MEDIAPIPE else 'Image successfully processed',
        'saved_path': filepath,
        'saved_filename': unique_filename,
        'image_url': f'/captured/{unique_filename}',
        'human_detected': human_detected,
        'human_probability': round(float(human_probability), 4),
        'strong_core_landmarks': strong_core,
        'avg_core_visibility': round(float(avg_core_visibility), 4),
        'avg_all_visibility': round(float(avg_all_visibility), 4),
        'landmarks_count': len(landmarks_data),
        'landmarks': landmarks_data
    }
    r = jsonify(payload)
    return _corsify(r), 200

if __name__ == '__main__':
    use_ssl = os.environ.get('SMARTFITAO_SSL', '').strip().lower() in ('1', 'true', 'yes', 'on')
    port = int(os.environ.get('CAMERA_APP_PORT', '5000'))
    scheme = 'https' if use_ssl else 'http'
    print(f"\n--- SERVER RUNNING ---")
    print(f"  Open in browser: {scheme}://127.0.0.1:{port}/")
    print(f"  On this network: {scheme}://{get_local_ip()}:{port}/")
    print(f"----------------------\n")
    kw = dict(host='0.0.0.0', port=port, debug=True)
    if use_ssl:
        kw['ssl_context'] = 'adhoc'
    app.run(**kw)
