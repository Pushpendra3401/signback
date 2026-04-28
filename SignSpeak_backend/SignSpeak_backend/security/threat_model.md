# SignSpeak Backend – Threat Model

## Assets
| Asset | Sensitivity |
|-------|-------------|
| Firebase ID tokens | High – grant account access |
| Agora App Certificate | Critical – must stay secret |
| User video/audio media | High – PII |
| Firestore chat metadata | Medium |
| ML model weights | Medium |

## Trust Boundaries
1. **Flutter App → Backend APIs** – public internet; Firebase auth required.
2. **Backend → Firebase/Firestore** – service account, VPC-SC recommended in prod.
3. **Backend → Agora** – server-to-server; App Certificate never exposed to clients.

## Threat Table (STRIDE)

| ID | Threat | Category | Mitigation |
|----|--------|----------|-----------|
| T1 | Token replay / stolen Bearer token | Spoofing | Short TTL (1h), Firebase revocation |
| T2 | Unauthenticated access to AI endpoints | Elevation | `require_auth` on every non-probe route |
| T3 | Channel participant bypass (access other users' RTC tokens) | Elevation | Firestore participant check in token server |
| T4 | DoS on `/emotion` or `/gesture` (compute-heavy) | Denial of Service | Rate limiting (60 req/min), Cloud Armor WAF |
| T5 | Malicious image input (adversarial ML attack) | Tampering | Input size validation, model robustness |
| T6 | PII leakage in logs | Information Disclosure | Redact UID/email from log messages |
| T7 | Secret Manager secret exfiltration | Disclosure | IAM least-privilege, audit logs |
| T8 | SSRF via user-controlled URLs | Tampering | No URL fetch from user input |
| T9 | Dependency supply-chain attack | Tampering | Pinned versions, Dependabot |
| T10 | Replay of expired Agora token | Spoofing | Server-side expiry check, short TTLs |

## Residual Risks
- Adversarial ML inputs on emotion/gesture endpoints: accept as low risk for v1; add input validation in v2.
- Agora token HMAC uses SHA-256 (not Agora's official SDK); replace before production.
