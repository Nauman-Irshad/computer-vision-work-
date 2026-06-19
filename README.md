# Computer Vision (Camera Work)

Live **BlazePose** body scan — 33 landmarks, posture check, auto-capture. AI runs **in the browser** (MediaPipe CDN). Works on **Vercel** without Python ML.

## Live demo (Vercel)

After deploy, open your Vercel URL in **Chrome/Edge** and allow camera.

## Deploy to Vercel

1. Push this repo to GitHub: [Nauman-Irshad/computer-vision-work-](https://github.com/Nauman-Irshad/computer-vision-work-)
2. Go to [vercel.com/new](https://vercel.com/new) → Import the repo
3. **Framework preset:** Other (no framework)
4. **Build command:** `npm run build` (syncs `templates/index.html` → `index.html`)
5. **Output directory:** `.` (root)
6. Deploy

Or CLI:

```bash
npm i -g vercel
cd "Computer Vision (Camera Work)"
vercel
```

## Local dev (Windows)

```powershell
cd "Computer Vision (Camera Work)"
pip install -r requirements.txt
$env:SMARTFITAO_HTTP='1'
$env:CAMERA_APP_PORT='5000'
python app.py
```

Open http://127.0.0.1:5000/

## How it works

| Layer | Local | Vercel |
|-------|--------|--------|
| UI + camera | `index.html` | `index.html` (static) |
| Pose AI | MediaPipe BlazePose (browser CDN) | Same |
| Save photo | Flask `/analyze` + `images/` | Browser auto-download |
| Verify pose | Browser + optional Flask | `/api/analyze` serverless |

## Capture rules

- **33/33** strong landmark dots (green)
- **Posture** OK (full body in frame)
- **Auto-capture** after ~1.8s hold still
- **STAND HERE** shadow guides placement

## Repo layout

```
index.html          ← Vercel entry (copy of templates/index.html)
templates/index.html ← Flask local + source of truth
api/analyze.js      ← Vercel serverless verify
app.py              ← Local Flask server only
vercel.json
package.json
```

After editing UI, run `npm run build` or copy `templates/index.html` to `index.html` before deploy.
