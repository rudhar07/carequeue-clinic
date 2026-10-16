# Kubernetes bootstrap

CareQueue runs on Kubernetes as one Helm release (`helm/carequeue`). This folder
has what has to exist **before** the chart: the namespace and the local kind
cluster definition.

| File | What it is |
|------|------------|
| `namespace.yaml` | Namespace `carequeue` with labels, including Pod Security Admission `restricted` (every CareQueue pod is non-root, drops all capabilities and uses the `RuntimeDefault` seccomp profile, so the strictest built-in profile is enforced). |
| `kind-config.yaml` | One-node kind cluster. Node label `ingress-ready=true` + port mappings: ingress-nginx is reachable on `http://localhost:8088` and `https://localhost:8448`. |

## Bootstrap order

```
1. cluster          kind create cluster --name cq --config k8s/kind-config.yaml
2. namespace        kubectl apply -f k8s/namespace.yaml
3. ingress-nginx    kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.15.1/deploy/static/provider/kind/deploy.yaml
4. metrics-server   helm upgrade --install metrics-server metrics-server --repo https://kubernetes-sigs.github.io/metrics-server/ \
                      --version 3.14.0 -n kube-system --set 'args={--kubelet-insecure-tls}'
5. monitoring       scripts/monitoring-up.sh   (kube-prometheus-stack + the Grafana dashboard, see monitoring/README.md)
6. the app          scripts/deploy-local.sh    (docker build, kind load, helm upgrade --install)
```

Steps 1-4 are `scripts/kind-up.sh`. Why this order:

- The **Ingress** resource is only configuration: without the ingress-nginx
  controller nothing serves it.
- The **HPA** reads CPU from metrics-server. Without it, `kubectl get hpa` shows
  `cpu: <unknown>/60%` (see troubleshooting case 5). kind's kubelet uses a
  self-signed certificate, hence `--kubelet-insecure-tls` (local clusters only).
- The chart renders its `ServiceMonitor` and `PrometheusRule` only when the
  Prometheus Operator CRDs exist (`.Capabilities.APIVersions.Has`). Install
  monitoring before the app, or run `helm upgrade` again afterwards.
- CI (`.github/workflows/ci-cd.yml`, deploy job) does steps 1, 3 and 6 on a
  fresh kind cluster with ports 80/443 and the GHCR images; no monitoring there.

## Quick start (local)

```bash
export KUBECONFIG="$HOME/.kube/kind-cq.yaml"   # optional: a separate kubeconfig for this cluster
scripts/kind-up.sh
scripts/monitoring-up.sh
scripts/deploy-local.sh
curl http://localhost:8088/api/info
curl -H 'Host: carequeue.local' http://localhost:8088/api/doctors
helm test carequeue -n carequeue --logs
```

Tear down: `kind delete cluster --name cq`.

## What the chart deploys

| Object | Name | Notes |
|--------|------|-------|
| Deployment | `carequeue-backend` | FastAPI, 2 replicas (HPA 2-6), `wait-for-db` initContainer, startup/liveness `/health`, readiness `/ready` |
| Deployment | `carequeue-frontend` | nginx-unprivileged, 2 replicas (HPA 2-4), proxies `/api` to `carequeue-backend:8000` |
| StatefulSet | `carequeue-postgresql` | PostgreSQL 17 + 1Gi PVC (`data-carequeue-postgresql-0`) |
| Services (ClusterIP) | `carequeue-backend` (8000), `carequeue-frontend` (80), `carequeue-postgresql` (5432), `carequeue-postgresql-hl` (headless) | named ports `http` / `postgresql` |
| Ingress | `carequeue` | class nginx; host `carequeue.local` + a host-less rule; `/api` → backend, `/` → frontend |
| HPA / PDB | `carequeue-backend`, `carequeue-frontend` | autoscaling/v2 CPU; PDB `minAvailable: 1` |
| Jobs (hooks) | `carequeue-migrate`, `carequeue-seed` | Alembic once per release; idempotent demo data |
| ConfigMap / Secret | `carequeue-config`, `carequeue-db` | Secret holds FAKE demo credentials; `database.existingSecret` for real ones |
| ServiceMonitor / PrometheusRule | `carequeue-backend`, `carequeue-alerts` | only when the Prometheus Operator CRDs exist |
| Test pod | `carequeue-test-connection` | `helm test`: backend `/ready` + `/health`, frontend `/api/info` through the nginx proxy |

Chart details and the reasoning behind the choices: `helm/carequeue/values.yaml` (comments) and
the template headers (`templates/job-migrate.yaml` explains the migration hook).
