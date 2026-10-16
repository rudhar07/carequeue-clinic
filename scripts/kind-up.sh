#!/usr/bin/env bash
# Create the local kind cluster and install the cluster add-ons CareQueue needs:
#   1. kind cluster "cq" (k8s/kind-config.yaml: ingress on localhost:8088/8448)
#   2. namespace carequeue (k8s/namespace.yaml)
#   3. ingress-nginx (kind provider manifest, same version as CI)
#   4. metrics-server (needed by the HPA; --kubelet-insecure-tls because kind's
#      kubelet serves a self-signed certificate)
# Monitoring is a separate step: scripts/monitoring-up.sh.
#
#   scripts/kind-up.sh
#   KUBECONFIG=/path/to/private-kubeconfig scripts/kind-up.sh   # keep ~/.kube/config untouched
set -euo pipefail

CLUSTER="${CLUSTER:-cq}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
INGRESS_NGINX_VERSION="${INGRESS_NGINX_VERSION:-controller-v1.15.1}"
METRICS_SERVER_CHART_VERSION="${METRICS_SERVER_CHART_VERSION:-3.14.0}"
KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
export KUBECONFIG

if kind get clusters 2>/dev/null | grep -qx "${CLUSTER}"; then
  echo "kind cluster ${CLUSTER} already exists"
  kind export kubeconfig --name "${CLUSTER}" --kubeconfig "${KUBECONFIG}"
else
  kind create cluster --name "${CLUSTER}" --config "${ROOT}/k8s/kind-config.yaml" \
    --kubeconfig "${KUBECONFIG}" --wait 180s
fi
kubectl cluster-info

echo "--- namespace"
kubectl apply -f "${ROOT}/k8s/namespace.yaml"

echo "--- ingress-nginx ${INGRESS_NGINX_VERSION}"
kubectl apply -f "https://raw.githubusercontent.com/kubernetes/ingress-nginx/${INGRESS_NGINX_VERSION}/deploy/static/provider/kind/deploy.yaml"
kubectl -n ingress-nginx wait --for=condition=Complete job --all --timeout=180s
kubectl -n ingress-nginx wait --for=condition=Available deployment/ingress-nginx-controller --timeout=240s

echo "--- metrics-server ${METRICS_SERVER_CHART_VERSION}"
helm upgrade --install metrics-server metrics-server \
  --repo https://kubernetes-sigs.github.io/metrics-server/ \
  --version "${METRICS_SERVER_CHART_VERSION}" \
  --namespace kube-system \
  --set 'args={--kubelet-insecure-tls}' \
  --wait --timeout 5m

kubectl get nodes -o wide
kubectl get pods -A
echo "Cluster ${CLUSTER} is ready. Next: scripts/deploy-local.sh"
