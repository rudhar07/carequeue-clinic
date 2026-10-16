#!/usr/bin/env bash
# Build the CareQueue images, load them into the kind cluster and deploy the
# Helm chart with the dev values (local images, demo seed, ingress, HPA).
#
#   scripts/kind-up.sh          # once: cluster + ingress-nginx + metrics-server
#   scripts/deploy-local.sh     # build + kind load + helm upgrade --install
#   SKIP_BUILD=1 scripts/deploy-local.sh   # redeploy without rebuilding
#
# Then: http://localhost:8088/  (or http://carequeue.local:8088/ with an
# /etc/hosts entry "127.0.0.1 carequeue.local").
set -euo pipefail

CLUSTER="${CLUSTER:-cq}"
NAMESPACE="${NAMESPACE:-carequeue}"
RELEASE="${RELEASE:-carequeue}"
TAG="${TAG:-local}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
GIT_SHA="${GIT_SHA:-$(git -C "${ROOT}" rev-parse --short HEAD 2>/dev/null || echo local)}"

if [ -z "${SKIP_BUILD:-}" ]; then
  echo "--- docker build (GIT_SHA=${GIT_SHA})"
  docker build -t "carequeue-backend:${TAG}" --build-arg "GIT_SHA=${GIT_SHA}" "${ROOT}/backend"
  docker build -t "carequeue-frontend:${TAG}" "${ROOT}/frontend"
fi

echo "--- kind load docker-image (cluster ${CLUSTER})"
kind load docker-image --name "${CLUSTER}" "carequeue-backend:${TAG}" "carequeue-frontend:${TAG}"

echo "--- namespace"
kubectl apply -f "${ROOT}/k8s/namespace.yaml"

echo "--- helm upgrade --install ${RELEASE}"
helm upgrade --install "${RELEASE}" "${ROOT}/helm/carequeue" \
  --namespace "${NAMESPACE}" --create-namespace \
  -f "${ROOT}/helm/carequeue/values-dev.yaml" \
  --set-string backend.image.repository=carequeue-backend \
  --set-string backend.image.tag="${TAG}" \
  --set-string frontend.image.repository=carequeue-frontend \
  --set-string frontend.image.tag="${TAG}" \
  --set-string backend.env.GIT_SHA="${GIT_SHA}" \
  --wait --timeout 8m

kubectl -n "${NAMESPACE}" rollout status deployment/"${RELEASE}-backend" --timeout=180s
kubectl -n "${NAMESPACE}" rollout status deployment/"${RELEASE}-frontend" --timeout=180s
kubectl -n "${NAMESPACE}" get pods,svc,ingress,hpa -o wide
echo "Open http://localhost:8088/   API: curl http://localhost:8088/api/info"
