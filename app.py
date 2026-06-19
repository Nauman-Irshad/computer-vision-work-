import json
import os
import cv2
import random
import socket
import qrcode
from io import BytesIO
from types import SimpleNamespace
from flask import Flask, request, jsonify, render_template, send_file, send_from_directory
from werkzeug.utils import secure_filename
from datetime import datetime

app = Flask(__name__)


@app.after_request
def _camera_page_headers(response):
    """Allow camera in-page and when embedded from Flutter Web (Edge/Chrome)."""
    response.headers["Permissions-Policy"] = 'camera=(self "http://localhost:5177" "http://127.0.0.1:5177" "http://127.0.0.1:5003" "http://localhost:5003"), microphone=(self)'
    response.headers["Content-Security-Policy"] = "frame-ancestors 'self' http://localhost:5177 http://127.0.0.1:5177 http://127.0.0.1:5003 http://localhost:5003 https://*.vercel.app"
    if request.path.startswith('/captured/'):
        response.headers["Access-Control-Allow-Origin"] = "*"
    return response

# Indices used for “body present” scoring (nose, shoulders, hips, ankles).
_CORE_POSE_INDICES = (0, 11, 12, 23, 24, 27, 28)


def _landmarks_from_browser_pose_json(pose_data):
    """33 keypoints from live MediaPipe in the browser (pose_json form field)."""
    keypoints = pose_data.get("keypoints") or []
    if len(keypoints) < 33:
        return []
    out = []
    for kp in keypoints[:33]:
        out.append(
            SimpleNamespace(
                visibility=float(kp.get("visibility", 0) or 0),
                x=float(kp.get("x", 0) or 0),
                y=float(kp.get("y", 0) or 0),
                z=float(kp.get("z", 0) or 0),
            )
        )
    return out


def _count_strong_landmarks(lms, min_vis=0.55):
    if not lms or len(lms) < 33:
        return 0
    return sum(1 for i in range(33) if float(lms[i].visibility) >= min_vis)


def _validate_posture(lms):
    required = (0, 11, 12, 23, 24, 27, 28)
    for idx in required:
        lm = lms[idx]
        if float(lm.visibility) < 0.6:
            return False
        margin = 0.03
        if lm.x < margin or lm.x > (1 - margin) or lm.y < margin or lm.y > (1 - margin):
            return False
    sy = (lms[11].y + lms[12].y) / 2
    hy = (lms[23].y + lms[24].y) / 2
    ay = (lms[27].y + lms[28].y) / 2
    return hy >= sy and ay >= hy


def _validate_apose(lms):
    import math
    ids = (11, 12, 13, 14, 15, 16, 23, 24)
    for idx in ids:
        if float(lms[idx].visibility) < 0.45:
            return False
    ls, rs = lms[11], lms[12]
    le, re = lms[13], lms[14]
    lw, rw = lms[15], lms[16]
    lh, rh = lms[23], lms[24]
    if abs(rs.x - ls.x) < 0.07:
        return False
    left_dx, left_dy = le.x - ls.x, le.y - ls.y
    right_dx, right_dy = re.x - rs.x, re.y - rs.y
    if left_dy < 0.01 or right_dy < 0.01:
        return False
    if left_dx >= -0.015 or right_dx <= 0.015:
        return False
    left_ang = math.degrees(math.atan2(abs(left_dx), max(1e-4, left_dy)))
    right_ang = math.degrees(math.atan2(abs(right_dx), max(1e-4, right_dy)))
    if not (15 <= left_ang <= 62 and 15 <= right_ang <= 62):
        return False
    hip_mid = (lh.y + rh.y) / 2
    if lw.y < hip_mid - 0.28 or rw.y < hip_mid - 0.28:
        return False
    return True


def _browser_pose_verified(lms, min_strong=33):
    if not lms or len(lms) < 33:
        return False
    strong = _count_strong_landmarks(lms)
    return strong >= min_strong and _validate_posture(lms)


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
    # Live browser pose often has 33 points but strict score rejects — allow try-on.
    if len(lms) >= 33 and avg_all >= 0.35 and strong >= 3:
        detected = True
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
    resp = send_from_directory(UPLOAD_FOLDER, safe)
    resp.headers['Access-Control-Allow-Origin'] = '*'
    return resp

# Try to initialize MediaPipe Pose (Fails on Python 3.13 often due to missing 'solutions')
try:
    import mediapipe as mp
    mp_pose = mp.solutions.pose
    pose = mp_pose.Pose(
        static_image_mode=True,
        model_complexity=2,
        min_detection_confidence=0.65
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
    used_browser_pose = False

    pose_json_raw = request.form.get("pose_json")
    if pose_json_raw:
        try:
            pose_data = json.loads(pose_json_raw)
            lms = _landmarks_from_browser_pose_json(pose_data)
            if len(lms) >= 33:
                used_browser_pose = True
                human_probability, strong_core, avg_core_visibility, _ = (
                    _score_human_from_landmarks(lms)
                )
                human_detected = _browser_pose_verified(lms)
                strong_core = _count_strong_landmarks(lms)
                avg_all_visibility = sum(float(x.visibility) for x in lms) / 33.0
                for idx, landmark in enumerate(lms):
                    landmarks_data.append({
                        "id": idx,
                        "name": (pose_data.get("keypoints") or [{}])[idx].get(
                            "name", f"landmark_{idx}"
                        ),
                        "x": landmark.x,
                        "y": landmark.y,
                        "z": landmark.z,
                        "visibility": landmark.visibility,
                    })
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"pose_json parse failed: {e}")

    if not used_browser_pose and HAS_MEDIAPIPE:
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
    elif not used_browser_pose:
        # Fallback when server MediaPipe solutions API unavailable (Python 3.11+ pip)
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

    if used_browser_pose:
        msg = 'A-pose verified (browser BlazePose)' if human_detected else 'A-pose not matched — adjust arms and full body'
    elif HAS_MEDIAPIPE:
        msg = 'Image successfully processed'
    else:
        msg = 'Image processed (server pose fallback — use live dots before capture)'

    payload = {
        'message': msg,
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
    use_plain_http = os.environ.get('SMARTFITAO_HTTP', '').strip().lower() in (
        '1', 'true', 'yes', 'on'
    )
    port = int(os.environ.get('CAMERA_APP_PORT', '5003'))
    print(f"\n--- SERVER RUNNING ---")
    if use_plain_http:
        print(f"SMARTFITAO_HTTP=1  ->  HTTP (no SSL). Desktop test: http://127.0.0.1:{port}")
    else:
        print(f"Scan the QR code or visit https://{get_local_ip()}:{port} on your mobile device.")
    print(f"----------------------\n")
    if use_plain_http:
        app.run(host='0.0.0.0', port=port, debug=True)
    else:
        app.run(host='0.0.0.0', port=port, debug=True, ssl_context='adhoc')
