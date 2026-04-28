# SignSpeak Backend

Complete Python backend for the **SignSpeak** real-time sign-language communication app.  
Built with Flask, Firebase Admin SDK, MediaPipe, DeepFace, and deployed on Google Cloud Run.

---

## Architecture Overview

```
Flutter App
     │
     ▼  (Firebase ID token in every request)
┌─────────────────────────────────────────────┐
│            API Gateway (Cloud Armor/WAF)     │
└──────┬────────────────────────┬─────────────┘
       │                        │
       ▼                        ▼
┌──────────────┐     ┌───────────────────┐
│ Token Server │     │    AI Server      │
│  :8080       │     │    :8081          │
│              │     │                   │
│ POST /token  │     │ POST /translate   │
│ GET  /health │     │ POST /emotion     │
│ GET  /ready  │     │ POST /gesture     │
└──────┬───────┘     │ POST /speech-to-text│
       │             │ POST /text-to-sign│
       │             │ POST /tts         │
       │             │ GET  /health      │
       │             │ GET  /ready       │
       │             └────────┬──────────┘
       │                      │
       ▼                      ▼
┌─────────────────────────────────────────────┐
│         Firebase / Google Cloud             │
│  Firestore (chats, audit)  Cloud Storage    │
└─────────────────────────────────────────────┘
```

---

## Project Structure

```
SignSpeak_backend/
├── ai_server/
│   ├── config.py               # Environment-based configuration
│   ├── emotion_detection.py    # DeepFace facial emotion detection
│   ├── gesture_detection.py    # MediaPipe hand gesture detection
│   ├── firebase_service.py     # Firebase Storage & Firestore helpers
│   ├── voice_generator.py      # TTS via pyttsx3 or gTTS
│   ├── main.py                 # Flask app + all AI endpoints
│   ├── Dockerfile
│   └── README.md
├── token_server/
│   ├── server.py               # Flask app + /token endpoint
│   ├── auth_middleware.py      # Firebase token verification decorator
│   ├── firestore_client.py     # Channel participant & audit helpers
│   └── Dockerfile
├── config/
│   ├── .env.example            # Template – copy to .env and fill in
│   └── serviceAccountKey.json  # ← DO NOT commit; add to .gitignore
├── docs/
│   ├── envs.md                 # All environment variable reference
│   ├── runbook_ai_server.md    # AI server ops runbook
│   └── runbook_token_server.md # Token server ops runbook
├── gateway/
│   ├── api_config.yaml         # API Gateway route config
│   └── waf_rules.yaml          # Cloud Armor WAF rules
├── infra/
│   └── terraform/
│       ├── main.tf             # Cloud Run, IAM, Secret Manager
│       ├── variables.tf        # Input variables
│       └── outputs.tf          # Deployment URLs
├── observability/
│   ├── alerts.yaml             # Alert rule definitions
│   ├── dashboards.md           # Dashboard metric reference
│   └── otel_config.yaml        # OpenTelemetry Collector config
├── security/
│   ├── content_moderation.md   # Content moderation strategy
│   ├── privacy.md              # Privacy policy guidelines
│   └── threat_model.md         # STRIDE threat model
├── tests/
│   ├── unit/
│   │   ├── test_ai_server.py
│   │   └── test_token_server.py
│   ├── integration/
│   │   └── test_endpoints.py
│   └── load/
│       └── locustfile.py
├── docker-compose.yml          # Local development orchestration
└── requirements.txt            # All Python dependencies
```

---

## Prerequisites

- Python 3.10–3.11
- Docker & Docker Compose (for containerised local dev)
- Firebase project with Firestore and Storage enabled
- Agora account with an App ID and App Certificate
- (Optional) Terraform ≥ 1.5 for cloud deployment

---

## Quick Start (Local)

### 1. Clone and configure
```bash
git clone <repo-url>
cd signspeak/SignSpeak_backend
cp config/.env.example .env
# Edit .env with your Firebase project ID, Agora credentials, etc.
```

### 2. Add Firebase service account
Place your Firebase service account key at:
```
config/serviceAccountKey.json
```
> **Never commit this file.** It is listed in `.gitignore`.

### 3. Run with Docker Compose
```bash
docker-compose up
```

Services will be available at:
- Token Server: `http://localhost:8080`
- AI Server:    `http://localhost:8081`

### 4. Run locally (without Docker)
```bash
pip install -r requirements.txt

# Terminal 1 – Token server
cd token_server && python server.py

# Terminal 2 – AI server
cd ai_server && python main.py
```

---

## API Reference

### Authentication
All endpoints (except `/health` and `/ready`) require a Firebase ID token:
```
Authorization: Bearer <firebase-id-token>
```

### Token Server (`http://localhost:8080`)

#### `POST /token`
Generate an Agora RTC token.
```json
// Request
{ "channelId": "chat-abc123", "uid": "user-uid", "role": "publisher", "ttlSeconds": 3600 }

// Response
{ "token": "...", "role": "publisher", "expiresIn": 3600, "expiresAt": 1234567890, "channelId": "...", "uid": "..." }
```

### AI Server (`http://localhost:8081`)

#### `POST /translate`
```json
// Request
{ "text": "Hello", "source_lang": "en", "target_lang": "hi" }
// Response
{ "translated_text": "Hello", "source_lang": "en", "target_lang": "hi", "confidence": 1.0 }
```

#### `POST /emotion`
Send image as multipart file (`image`) or `{"image": "<base64>"}`.
```json
// Response
{ "label": "happy", "scores": {"happy": 0.82, "neutral": 0.14, "sad": 0.04}, "face_count": 1 }
```

#### `POST /gesture`
Send image as multipart file (`image`) or `{"image": "<base64>"}`.
```json
// Response
{ "hands": [{ "handedness": "Right", "gesture": "PEACE", "landmarks": [...] }], "hand_count": 1 }
```

#### `POST /tts`
```json
// Request
{ "text": "Hello World", "lang": "en" }
// Response: raw audio bytes (WAV or MP3)
```

#### `POST /speech-to-text`
Send audio as multipart file (`audio`) or raw body (`Content-Type: audio/wav`).
```json
// Response
{ "transcript": "...", "confidence": 0.95 }
```

#### `POST /text-to-sign`
```json
// Request
{ "text": "Good morning", "locale": "en-US" }
// Response
{ "sign_sequence": ["GOOD", "MORNING"], "locale": "en-US" }
```

---

## Running Tests

```bash
# Unit tests
python -m pytest tests/unit/ -v

# Integration tests
python -m pytest tests/integration/ -v

# Load tests (requires running servers)
pip install locust
locust -f tests/load/locustfile.py --host http://localhost:8081 --headless -u 50 -r 5 -t 60s
```

---

## Cloud Deployment (Terraform)

```bash
cd infra/terraform
terraform init
terraform plan -var="project_id=signspeak-20dff" -var="token_server_image=gcr.io/signspeak-20dff/token-server:latest" -var="ai_server_image=gcr.io/signspeak-20dff/ai-server:latest"
terraform apply
```

Outputs: `token_server_url`, `ai_server_url`, `backend_service_account`.

---

## Environment Variables

See [`docs/envs.md`](docs/envs.md) for a full reference.

---

## Security

- All endpoints are protected by Firebase ID token verification.
- Agora App Certificate is stored in Google Secret Manager.
- See [`security/threat_model.md`](security/threat_model.md) for the STRIDE threat model.
- See [`security/privacy.md`](security/privacy.md) for data privacy guidelines.

---

## Contributing

1. Fork the repo and create a feature branch.
2. Install dependencies: `pip install -r requirements.txt`.
3. Run tests before submitting a PR: `python -m pytest tests/`.
4. Ensure no secrets are committed (check `.gitignore`).
