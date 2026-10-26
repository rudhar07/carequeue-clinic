#!/usr/bin/env bash
# Install Argo CD (non-HA) into the local cluster and hand CareQueue to it.
# Run after scripts/kind-up.sh and scripts/monitoring-up.sh (the ServiceMonitor
# needs the Prometheus Operator CRDs).
#
#   scripts/argocd-up.sh
#   KUBECONFIG=/path/to/private-kubeconfig scripts/argocd-up.sh
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
ARGOCD_VERSION="${ARGOCD_VERSION:-stable}"

kubectl create namespace argocd --dry-run=client -o yaml | kubectl apply -f -
kubectl apply -n argocd --server-side --force-conflicts \
  -f "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGOCD_VERSION}/manifests/install.yaml"
kubectl -n argocd rollout status deploy/argocd-server --timeout=300s
kubectl -n argocd rollout status deploy/argocd-repo-server --timeout=300s
kubectl -n argocd rollout status statefulset/argocd-application-controller --timeout=300s

# Poll Git every 30 s instead of the default 3 minutes (demo-friendly).
kubectl -n argocd patch configmap argocd-cm --type merge -p '{"data":{"timeout.reconciliation":"30s"}}'
kubectl -n argocd rollout restart statefulset/argocd-application-controller

kubectl apply -n argocd -f "${ROOT}/gitops/argocd-application.yaml"
echo "Waiting for the CareQueue Application to be Synced and Healthy…"
for _ in $(seq 1 60); do
  s=$(kubectl -n argocd get application carequeue -o jsonpath='{.status.sync.status}/{.status.health.status}' 2>/dev/null || true)
  echo "  ${s}"
  [[ "${s}" == "Synced/Healthy" ]] && break
  sleep 10
done
kubectl -n carequeue get pods,svc,ingress
echo "Argo CD UI:  kubectl -n argocd port-forward svc/argocd-server 8443:443   (user admin)"
echo "Password:    kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
