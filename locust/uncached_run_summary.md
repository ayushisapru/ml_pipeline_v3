# Uncached Locust Run (2025-10-20)

- **Command**: `docker compose run --rm -e LOCUST_HOST=http://inference:8000 -e LOCUST_MODE=headless -e LOCUST_ENABLE_PREDICT_CACHE=0 -e PREDICT_PAYLOAD_MODE=synthetic locust -f /mnt/locust/locustfile.py --headless -u 40 -r 4 -t 20s`
- **Duration**: 20s ramp to 40 users (4 users/s)
- **Aggregated throughput**: 2.76 req/s (54 total requests, 0 failures)
- **POST /predict**: 11 requests, avg 105 ms (p95 ≈ 250 ms), throughput 0.56 req/s, 0 failures
- **GET /healthz-warm**: 40 requests, avg 106 ms, 0 failures
- **Notes**: Cache disabled via `ENABLE_PREDICT_CACHE=0` and `DISABLE_INFERENCE_CACHE=1` in `docker-compose.yaml`; inference rebuilt before the run.
