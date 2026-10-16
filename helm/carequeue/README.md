# Helm chart: carequeue

Deploys CareQueue (FastAPI backend, React/nginx frontend, PostgreSQL) with an
Ingress, HPAs, PDBs, a migration hook, an optional demo seed, a `helm test`,
and (when the Prometheus Operator is installed) a ServiceMonitor and alert rules.

```bash
# local kind cluster (images built and kind-loaded by scripts/deploy-local.sh)
helm upgrade --install carequeue helm/carequeue -n carequeue --create-namespace \
  -f helm/carequeue/values-dev.yaml
helm test carequeue -n carequeue --logs

# CI (.github/workflows/ci-cd.yml, deploy job): GHCR images tagged with the commit SHA
helm upgrade --install carequeue helm/carequeue -n carequeue --create-namespace \
  --set-string backend.image.repository=ghcr.io/rudhar07/carequeue-backend \
  --set-string backend.image.tag=<sha> \
  --set-string frontend.image.repository=ghcr.io/rudhar07/carequeue-frontend \
  --set-string frontend.image.tag=<sha> \
  --set-string backend.env.GIT_SHA=<sha> \
  --set 'imagePullSecrets[0].name=ghcr' \
  --set ingress.enabled=true --set-string ingress.className=nginx \
  --set-string ingress.host=carequeue.local --set postgresql.enabled=true \
  --wait --timeout 8m
```

| Values file | For |
|-------------|-----|
| `values.yaml` | Defaults (GHCR images, in-chart PostgreSQL with a FAKE password, Ingress on, HPA 2-6, demo seed on) |
| `values-dev.yaml` | kind: local `carequeue-*:local` images, HPA scale-down window 60 s instead of 300 s for the demo |
| `values-prod.yaml` | EKS: RDS via `database.host` + `database.existingSecret`, no seed, 3+ replicas spread over zones, TLS Ingress |

## Main values

| Key | Default | Notes |
|-----|---------|-------|
| `backend.image.repository` / `.tag` | `ghcr.io/rudhar07/carequeue-backend` / `""` | empty tag = `Chart.appVersion` |
| `frontend.image.repository` / `.tag` | `ghcr.io/rudhar07/carequeue-frontend` / `""` | |
| `imagePullSecrets` | `[]` | e.g. `[{name: ghcr}]` |
| `backend.env.*` | `GIT_SHA`, `APP_VERSION`, `LOG_LEVEL`, `CLINIC_TIMEZONE`, `CORS_ORIGINS` | rendered into the ConfigMap; `GIT_SHA` "" = image tag. Shown by `GET /api/info` |
| `backend.replicaCount` / `frontend.replicaCount` | `2` / `2` | with the HPA on, upgrades keep the HPA's current count (`lookup`) |
| `backend.resources` | req `100m/160Mi`, lim `500m/320Mi` | requests are what the HPA percentage is based on |
| `backend.probes.{startup,liveness,readiness}` | `/health`, `/health`, `/ready` | readiness fails (503) while the DB is down; liveness never touches the DB |
| `backend.autoscaling` | on, 2-6, 60% CPU, scale-down window 300 s | `frontend.autoscaling`: on, 2-4, 70% |
| `*.podDisruptionBudget` | `minAvailable: 1` | |
| `migrations.enabled` | `true` | hook Job `alembic upgrade head`, post-install + pre-upgrade |
| `seed.enabled` / `seed.demoQueue` | `true` / `true` | hook Job `python -m app.seed --demo-queue` (idempotent) |
| `postgresql.enabled` | `true` | StatefulSet + 1Gi PVC + ClusterIP and headless Services |
| `postgresql.auth.username` / `.password` | `carequeue` / FAKE demo value | only for kind/CI |
| `database.host` / `.existingSecret` | `""` / `""` | external DB; the Secret must hold `DATABASE_URL` |
| `ingress.enabled` / `.className` / `.host` | `true` / `nginx` / `carequeue.local` | `/api` → backend, `/` → frontend |
| `ingress.pathOnlyRule` | `true` | extra host-less rule so `http://localhost` works |
| `monitoring.serviceMonitor.*`, `monitoring.prometheusRule.*` | on, 15 s | only rendered when the CRDs exist |
| `tests.image` | `curlimages/curl:8.17.0` | `helm test` pod (kept after the run so `--logs` works) |

## Design notes

- **Migrations run once, in a hook Job**, not in every backend pod: with 2+
  replicas, parallel `alembic upgrade head` runs race on the first `CREATE TABLE`.
  The hook is `post-install` (the in-chart PostgreSQL does not exist yet during
  pre-install) and `pre-upgrade` (the schema is migrated before new pods roll
  out, and a failed migration stops the upgrade). Delete policy
  `before-hook-creation,hook-succeeded`. Full reasoning: `templates/job-migrate.yaml`.
- **`wait-for-db` initContainer** (backend, migrate, seed): waits until the
  database accepts TCP connections, so the backend does not crash-loop while
  PostgreSQL initialises. It uses the backend image, so nothing extra is pulled.
- **Security:** every pod runs as non-root (backend 10001, nginx 101, postgres
  70) with `readOnlyRootFilesystem`, all capabilities dropped,
  `allowPrivilegeEscalation: false`, `seccompProfile: RuntimeDefault` and no
  service-account token. Writable paths are `emptyDir`s (`/tmp`;
  `/etc/nginx/conf.d` for the rendered nginx config; the PostgreSQL socket
  directory). The namespace enforces Pod Security `restricted`.
- **Rollouts:** `maxUnavailable: 0`, `maxSurge: 1`; config/secret checksums on
  the backend pod template restart pods when settings change.
