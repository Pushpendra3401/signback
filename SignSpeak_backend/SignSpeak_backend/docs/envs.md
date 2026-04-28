# SignSpeak Backend – Environment Variables Reference

## Common Variables (Both Services)

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GOOGLE_APPLICATION_CREDENTIALS` | No* | – | Path to service account JSON. Falls back to `config/serviceAccountKey.json`, then ADC. |
| `FIREBASE_PROJECT_ID` | Yes | `signspeak-20dff` | GCP / Firebase project ID |
| `LOG_LEVEL` | No | `INFO` | Python logging level: DEBUG, INFO, WARNING, ERROR |
| `FLASK_DEBUG` | No | `false` | Enable Flask debug mode (never in prod) |

## Token Server Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AGORA_APP_ID` | Yes | – | Agora App ID from Agora Console |
| `AGORA_APP_CERTIFICATE` | Yes | – | Agora App Certificate (keep secret) |
| `TOKEN_TTL_SECONDS` | No | `3600` | Default token lifetime in seconds |
| `TOKEN_SERVER_HOST` | No | `0.0.0.0` | Bind address |
| `TOKEN_SERVER_PORT` | No | `8080` | Bind port |

## AI Server Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FIREBASE_STORAGE_BUCKET` | No | `{PROJECT_ID}.appspot.com` | GCS bucket name |
| `EMOTION_BACKEND` | No | `opencv` | DeepFace detector: opencv, ssd, mtcnn, retinaface |
| `EMOTION_ENFORCE_DETECTION` | No | `false` | Fail if no face detected |
| `GESTURE_MIN_DETECTION_CONFIDENCE` | No | `0.6` | MediaPipe min detection confidence |
| `GESTURE_MIN_TRACKING_CONFIDENCE` | No | `0.5` | MediaPipe min tracking confidence |
| `GESTURE_MAX_NUM_HANDS` | No | `2` | Max simultaneous hands to track |
| `TTS_USE_GTTS` | No | `false` | Use gTTS (online) instead of pyttsx3 |
| `TTS_GTTS_LANG` | No | `en` | gTTS language code |
| `TTS_RATE` | No | `150` | pyttsx3 speech rate (words per minute) |
| `TTS_VOLUME` | No | `1.0` | pyttsx3 volume (0.0–1.0) |
| `RATE_LIMIT_PER_MINUTE` | No | `60` | API rate limit per user uid |
| `AI_SERVER_HOST` | No | `0.0.0.0` | Bind address |
| `AI_SERVER_PORT` | No | `8081` | Bind port |

## Environments

| Env | Config File | Firestore DB | Notes |
|-----|-------------|--------------|-------|
| `dev` | `.env` | `(default)` | Local docker-compose |
| `staging` | Secret Manager | `staging` | Cloud Run staging revision |
| `prod` | Secret Manager | `(default)` | Cloud Run latest revision |
