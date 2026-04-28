# AI Server Runbook

## Startup Checklist
1. Ensure `GOOGLE_APPLICATION_CREDENTIALS` or `config/serviceAccountKey.json` is present.
2. Verify `FIREBASE_PROJECT_ID` and `FIREBASE_STORAGE_BUCKET` are set.
3. Run health check: `curl http://localhost:8081/health` → `{"status":"ok"}`.
4. Run readiness: `curl http://localhost:8081/ready` → `{"ready":true}`.
5. Check that MediaPipe models are downloaded (first `/gesture` call will lazy-load).
6. Check that DeepFace models are cached (first `/emotion` call will download ≈100MB).

## Starting Locally
```bash
cd SignSpeak_backend
pip install -r requirements.txt
cd ai_server
python main.py
```

## Starting with Docker Compose
```bash
cd SignSpeak_backend
cp config/.env.example .env   # fill in your values
docker-compose up ai-server
```

## Common Failures

### OOM / Killed by kernel
- **Cause**: DeepFace model loading exceeds container memory.
- **Action**: Increase Cloud Run memory limit to ≥2Gi. Switch `EMOTION_BACKEND=opencv` (lightest).

### `RuntimeError: mediapipe is not installed`
- **Action**: `pip install mediapipe==0.10.14` or rebuild Docker image.

### `RuntimeError: DeepFace is not installed`
- **Action**: `pip install deepface tf-keras` or rebuild Docker image.

### High p95 latency on `/emotion`
- **Cause**: DeepFace cold-start model load (~3s first call).
- **Action**: Use Cloud Run min-instances ≥ 1. Pre-warm by calling `/emotion` on startup.

### 401 on all endpoints
- **Cause**: Firebase credentials missing or project ID mismatch.
- **Action**: Check `GOOGLE_APPLICATION_CREDENTIALS` and `FIREBASE_PROJECT_ID`. Re-verify token with Firebase Console.

## Scaling
- Cloud Run: `min_instance_count = 1`, `max_instance_count = 5`.
- CPU-bound (MediaPipe/DeepFace): deploy on 2-vCPU instances.
- For GPU support: use GKE with GPU node pools and a custom GPU-enabled image.

## CPU Fallback
If GPU-accelerated MediaPipe is unavailable, set `GESTURE_MIN_DETECTION_CONFIDENCE=0.5` for slightly better CPU performance. All current models run on CPU.
