# 05 — Multi-Environment Deployment Guide (`dev` & `prod` on `10.100.109.9`)

## 1. Environment Isolation Matrix
Both `dev` and `prod` environments run side-by-side on `10.100.109.9` using isolated Docker Compose project names, container names, bridge networks, volumes, and host ports:

| Setting | DEV (`--env dev`) | PROD (`--env prod`) |
| :--- | :--- | :--- |
| **Remote Path** | `~/it-network-support-agent-dev` | `~/it-network-support-agent-prod` |
| **Compose Project (`-p`)** | `it-net-support-dev` | `it-net-support-prod` |
| **App Container** | `it-net-agent-dev` | `it-net-agent-prod` |
| **Postgres Container** | `it-net-postgres-dev` | `it-net-postgres-prod` |
| **Redis Container** | `it-net-redis-dev` | `it-net-redis-prod` |
| **Docker Network** | `it-net-network-dev` | `it-net-network-prod` |
| **Docker Volumes** | `it-net-pgdata-dev`, `it-net-redisdata-dev` | `it-net-pgdata-prod`, `it-net-redisdata-prod` |
| **Web / API Host Port** | `8085` | `8084` |
| **Postgres Host Port** | `5435` | `5434` |
| **Redis Host Port** | `6385` | `6384` |
| **vLLM Endpoint** | `http://10.100.109.9:8002` | `http://10.100.109.9:8002` |

## 2. Deployment Commands
```bash
# Deploy DEV stack
./deploy.sh --env dev

# Deploy PROD stack
./deploy.sh --env prod

# Inspect container status
./deploy.sh --env dev --status
./deploy.sh --env prod --status

# Stream live logs
./deploy.sh --env dev --logs
./deploy.sh --env prod --logs
```
