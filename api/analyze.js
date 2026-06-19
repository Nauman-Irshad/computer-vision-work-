/** Vercel serverless — trusts browser BlazePose pose_json (no Python/MediaPipe). */

function lmAt(keypoints, idx) {
  const kp = keypoints[idx];
  if (!kp) return null;
  return {
    x: Number(kp.x) || 0,
    y: Number(kp.y) || 0,
    visibility: Number(kp.visibility) || 0,
  };
}

function countStrong(keypoints, minVis = 0.55) {
  let n = 0;
  for (let i = 0; i < Math.min(keypoints.length, 33); i++) {
    if ((Number(keypoints[i].visibility) || 0) >= minVis) n++;
  }
  return n;
}

function validatePosture(keypoints) {
  const required = [0, 11, 12, 23, 24, 27, 28];
  for (const id of required) {
    const lm = lmAt(keypoints, id);
    if (!lm || lm.visibility < 0.6) return false;
    const margin = 0.03;
    if (lm.x < margin || lm.x > 1 - margin || lm.y < margin || lm.y > 1 - margin) return false;
  }
  const sy = (lmAt(keypoints, 11).y + lmAt(keypoints, 12).y) / 2;
  const hy = (lmAt(keypoints, 23).y + lmAt(keypoints, 24).y) / 2;
  const ay = (lmAt(keypoints, 27).y + lmAt(keypoints, 28).y) / 2;
  return hy >= sy && ay >= hy;
}

export default async function handler(req, res) {
  res.setHeader('Access-Control-Allow-Origin', '*');
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS');
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type');

  if (req.method === 'OPTIONS') return res.status(204).end();
  if (req.method !== 'POST') return res.status(405).json({ error: 'Method not allowed' });

  try {
    const body = req.body || {};
    const poseJson = body.pose_json || {};
    const keypoints = Array.isArray(poseJson.keypoints) ? poseJson.keypoints : [];
    const strong = countStrong(keypoints);
    const postureOk = validatePosture(keypoints);
    const human_detected = keypoints.length >= 33 && strong >= 33 && postureOk;
    const ts = new Date().toISOString().replace(/[-:TZ.]/g, '').slice(0, 14);
    const saved_filename = `auto_capture_${ts}.jpg`;

    const landmarks = keypoints.slice(0, 33).map((kp, i) => ({
      id: i,
      name: kp.name || `landmark_${i}`,
      x: kp.x,
      y: kp.y,
      z: kp.z != null ? kp.z : 0,
      visibility: kp.visibility != null ? kp.visibility : 0,
    }));

    return res.status(200).json({
      message: human_detected
        ? 'Body verified (browser BlazePose)'
        : 'Need 33 green landmarks and good posture',
      saved_filename,
      image_url: null,
      human_detected,
      human_probability: human_detected ? 0.96 : Math.min(0.5, strong / 33),
      strong_core_landmarks: strong,
      avg_core_visibility: strong / 33,
      avg_all_visibility: strong / 33,
      landmarks_count: landmarks.length,
      landmarks,
      posture_ok: postureOk,
    });
  } catch (err) {
    return res.status(500).json({ error: String(err.message || err) });
  }
}
