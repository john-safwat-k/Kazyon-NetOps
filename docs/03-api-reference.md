# 03 — API & WebSocket Reference

## Health & System Status

### `GET /api/health`
- **Auth:** Public (used by Docker healthcheck and `deploy.sh`)
- **Response (`200 OK`):**
  ```json
  {
    "status": "ok",
    "service": "IT Network Support AI Agent",
    "environment": "development",
    "env_slug": "dev",
    "version": "1.0.0",
    "vllm_base_url": "http://10.100.109.9:8002",
    "vllm_model": "google/gemma-4-26B-A4B-it"
  }
  ```

### `GET /api/v1/system/vllm-status`
- **Description:** Probes `http://10.100.109.9:8002/v1/models` to verify `Gemma 4 26B A4B` readiness.
