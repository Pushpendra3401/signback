# SignSpeak Backend – Privacy Policy Guidelines

## Data Collected
| Data Type | Purpose | Retention |
|-----------|---------|-----------|
| Firebase UID | Identity | Until account deleted |
| Display name, avatar URL | Profile | Until account deleted |
| Chat channel membership | Call routing | 90 days after last activity |
| Token audit records | Security / compliance | 30 days |
| Video/audio media (transient) | Sign translation, STT | Not persisted; processed in-memory |
| Emotion / gesture results | In-call UX | Not persisted; returned to client |

## Data Minimisation
- The backend never stores raw video frames or audio recordings.
- Only metadata (channel ID, participants, timestamps) is persisted.
- No third-party analytics SDKs are embedded in backend services.

## User Rights
| Right | Mechanism |
|-------|-----------|
| Access | User can request a data export via support (future: self-service API) |
| Deletion | DELETE /users/{uid} cascade-deletes Firestore documents and Storage objects |
| Rectification | PUT /profile updates only the fields provided |
| Portability | Data export as JSON |

## Consent
- User consents to data processing on sign-up (Firebase Auth + Terms of Service).
- Regional storage residency is controlled via Firebase project region settings.

## Security of Personal Data
- Data in transit: TLS 1.2+ enforced by GCP Load Balancer / Cloud Run.
- Data at rest: AES-256 encryption by default in Firestore and Cloud Storage.
- Access logs: Cloud Audit Logs enabled for all data-plane operations.
