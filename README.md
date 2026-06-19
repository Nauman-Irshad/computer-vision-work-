# Computer Vision (Camera Work)

Live **BlazePose** body scan — 33 landmarks, posture check, auto-capture. AI runs **in the browser** (MediaPipe CDN). Works on **Vercel** without Python ML.

## Live demo (Vercel)

After deploy, open your Vercel URL in **Chrome/Edge** and allow camera.

## Deploy to Vercel

1. Push this repo to GitHub: [Nauman-Irshad/computer-vision-work-](https://github.com/Nauman-Irshad/computer-vision-work-)
2. Go to [vercel.com/new](https://vercel.com/new) → Import the repo
3. **Framework preset:** Other (no framework)
4. **Build command:** `npm run build` (creates `public/index.html`)
5. **Output directory:** `public`
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

> **Vercel note:** Python/Flask files are excluded via `.vercelignore`. Production uses browser MediaPipe + `/api/analyze` only (small bundle, no 450MB install).

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
public/index.html   ← Vercel output (built from templates/index.html)
templates/index.html ← Source + Flask local
api/analyze.js      ← Vercel serverless verify
app.py              ← Local Flask server only
vercel.json
package.json
build.cjs           ← npm run build → public/
```

After editing UI, run `npm run build` (updates `public/index.html`) before deploy.
