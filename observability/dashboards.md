# SignSpeak Backend – Monitoring Dashboards

## Token Server Dashboard

| Panel | Metric | Aggregation |
|-------|--------|-------------|
| Request rate | `http_requests_total{service="token-server"}` | per-minute rate |
| Error rate (5xx) | `http_server_error_rate{service="token-server"}` | ratio 0-1 |
| 401 rate | `http_401_rate{service="token-server"}` | ratio 0-1 |
| p50 latency | `http_request_duration_ms{service="token-server", quantile="0.5"}` | ms |
| p95 latency | `http_request_duration_ms{service="token-server", quantile="0.95"}` | ms |
| Tokens issued / min | `counter{name="tokens_issued",service="token-server"}` | per-minute rate |
| Active instances | `cloud_run_active_instances{service="token-server"}` | count |

## AI Server Dashboard

| Panel | Metric | Aggregation |
|-------|--------|-------------|
| Request rate | `http_requests_total{service="ai-server"}` | per-minute rate |
| Error rate (5xx) | `http_server_error_rate{service="ai-server"}` | ratio 0-1 |
| p50 latency | `http_request_duration_ms{service="ai-server", quantile="0.5"}` | ms |
| p95 latency | `http_request_duration_ms{service="ai-server", quantile="0.95"}` | ms |
| Emotion detections / min | `counter{endpoint="/emotion"}` | per-minute rate |
| Gesture detections / min | `counter{endpoint="/gesture"}` | per-minute rate |
| TTS requests / min | `counter{endpoint="/tts"}` | per-minute rate |
| Translate requests / min | `counter{endpoint="/translate"}` | per-minute rate |
| Memory utilization | `cloud_run_memory_utilization{service="ai-server"}` | % |
| CPU utilization | `cloud_run_cpu_utilization{service="ai-server"}` | % |
| Active instances | `cloud_run_active_instances{service="ai-server"}` | count |

## Infrastructure Dashboard

| Panel | Metric |
|-------|--------|
| Firestore reads / min | `firestore_reads_total` |
| Firestore writes / min | `firestore_writes_total` |
| Storage upload bytes | `storage_upload_bytes_total` |
| Storage download bytes | `storage_download_bytes_total` |

## Recommended Dashboarding Tool
- **Google Cloud Monitoring** (built-in with Cloud Run)
- **Grafana** connected via the Google Cloud Monitoring data source
- **Locust** for real-time load-test results
