# GitOps with Argo CD

Argo CD deploys CareQueue from this Git repository. Nobody runs `helm` or `kubectl apply` for the app:
the cluster converges to whatever is on `main`.

```
 git push ──► GitHub (helm/carequeue on main) ◄── Argo CD polls / compares
                                                     │
                                         sync (helm template + apply)
                                                     ▼
                                     namespace carequeue: Deployments, Services,
                                     Ingress, HPA, Postgres, ServiceMonitor…
```

| Idea | How CareQueue does it |
|---|---|
| Git is the source of truth | `gitops/argocd-application.yaml` points at `helm/carequeue` on `main` |
| Declarative | The Helm chart and values describe the desired state; Argo CD renders and applies them |
| Automated sync | `syncPolicy.automated`: a new commit is rolled out without manual steps |
| Self-heal | `selfHeal: true`: a manual `kubectl scale` or `kubectl edit` is reverted to Git |
| Prune | `prune: true`: a resource deleted from Git is deleted from the cluster |
| Immutable images | Images come from GHCR, tagged with the commit SHA that CI built them from |

## Run it (local kind cluster)

```bash
scripts/kind-up.sh                         # kind + ingress-nginx + metrics-server
scripts/monitoring-up.sh                   # Prometheus + Grafana (CRDs for the ServiceMonitor)
scripts/argocd-up.sh                       # installs Argo CD and applies the Application
argocd app get carequeue                   # Synced / Healthy
```

Argo CD UI: `kubectl -n argocd port-forward svc/argocd-server 8443:443`, then https://localhost:8443
(user `admin`, password: `argocd admin initial-password -n argocd`).

## The GitOps flow, step by step

1. A developer pushes to `main`. CI tests, scans and pushes `carequeue-backend:<sha>` and `carequeue-frontend:<sha>` to GHCR.
2. To release that build, the image tags in `gitops/argocd-application.yaml` are changed to `<sha>`, committed and pushed.
3. Argo CD notices that Git and the cluster differ (OutOfSync), renders the chart, applies the change and rolls the pods.
4. If someone changes the cluster by hand, self-heal puts it back the way Git says.
