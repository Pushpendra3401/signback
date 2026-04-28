# SignSpeak Backend – Content Moderation

## Scope
All user-generated content passing through the backend:
- Images sent to `/emotion` and `/gesture` endpoints
- Text sent to `/translate`, `/text-to-sign`, and `/tts`
- Audio sent to `/speech-to-text`

## Detection Strategies

### Image Content
| Check | Method | Action |
|-------|--------|--------|
| NSFW / explicit content | Cloud Vision SafeSearch (optional add-on) | Reject with HTTP 422 |
| Oversized payload | Header `Content-Length` check (max 5 MB) | Reject with HTTP 413 |
| Non-image bytes | `cv2.imdecode` failure | Reject with HTTP 400 |

### Text Content
| Check | Method | Action |
|-------|--------|--------|
| Extremely long input | Max 2000 characters | Reject with HTTP 400 |
| Potential injection (prompt / SQL) | Pattern matching | Strip/sanitise before model |
| Hate speech / profanity | (future) Perspective API | Log and optionally reject |

### Audio Content
| Check | Method | Action |
|-------|--------|--------|
| Oversized file | Max 10 MB | Reject with HTTP 413 |
| Unsupported codec | FFprobe check (optional) | Reject with HTTP 415 |

## Reporting Workflow
1. Violations are logged to Cloud Logging with `moderation=true` label.
2. A Pub/Sub topic `signspeak-moderation-events` receives structured violation events.
3. A Cloud Function processes events and notifies the trust-and-safety team.

## Rate Limits as Moderation
- 60 requests/minute per authenticated UID enforced by WAF rules.
- Exceeding the limit returns HTTP 429 and triggers an alert.
