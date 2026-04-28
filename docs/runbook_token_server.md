# Token Server Runbook

## Startup Checklist
1. Set `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE` environment variables.
2. Ensure Firebase credentials are available (service account JSON or ADC).
3. Run health check: `curl http://localhost:8080/health` → `{"status":"ok"}`.

## Starting Locally
```bash
cd SignSpeak_backend/token_server
pip install -r ../requirements.txt
python server.py
```

## Starting with Docker Compose
```bash
cd SignSpeak_backend
cp config/.env.example .env   # fill in AGORA_APP_ID, AGORA_APP_CERTIFICATE
docker-compose up token-server
```

## Common Failures

### 5xx Spike
- **Cause**: Missing Agora credentials or Firestore unavailable.
- **Check**: `AGORA_APP_ID` and `AGORA_APP_CERTIFICATE` are set. View Cloud Run logs.
- **Action**: Rollback to the previous revision: `gcloud run services update-traffic signspeak-token-server --to-revisions=PREV=100`.

### Token Generation Errors (`500 Agora credentials are not configured`)
- **Cause**: Missing secrets at runtime.
- **Action**: Add secrets in Secret Manager and reference them in Cloud Run env config. Re-deploy.

### High 401 Rate
- **Cause**: Client sending expired or invalid Firebase tokens.
- **Action**: Ensure client refreshes token before expiry. Check Firebase project ID matches.

### Firestore Permission Denied
- **Cause**: Service account lacks `roles/datastore.user`.
- **Action**: Run `gcloud projects add-iam-policy-binding PROJECT_ID --member=serviceAccount:SA_EMAIL --role=roles/datastore.user`.

## Rollback Procedure
```bash
# List revisions
gcloud run revisions list --service signspeak-token-server --region us-central1

# Roll back to previous
gcloud run services update-traffic signspeak-token-server \
  --to-revisions=REVISION_NAME=100 \
  --region us-central1
```

## Inspecting Logs
```bash
gcloud logging read \
  "resource.type=cloud_run_revision AND resource.labels.service_name=signspeak-token-server" \
  --limit=50 --format=json | jq '.[].jsonPayload.message'
```
