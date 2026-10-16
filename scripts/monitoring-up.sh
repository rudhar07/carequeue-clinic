#!/usr/bin/env bash
# Install kube-prometheus-stack (Prometheus Operator, Prometheus, Alertmanager,
# Grafana, kube-state-metrics, node-exporter) into the "monitoring" namespace
# and provision the CareQueue Grafana dashboard.
#
#   scripts/monitoring-up.sh
# Then re-run "helm upgrade" of CareQueue (scripts/deploy-local.sh) if it was
# installed before the CRDs existed, so the ServiceMonitor and PrometheusRule
# get rendered.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
KPS_VERSION="${KPS_VERSION:-92.9.0}"

helm upgrade --install kps kube-prometheus-stack \
  --repo https://prometheus-community.github.io/helm-charts \
  --version "${KPS_VERSION}" \
  --namespace monitoring --create-namespace \
  -f "${ROOT}/monitoring/kube-prometheus-stack-values.yaml" \
  --wait --timeout 10m

# Dashboard as a ConfigMap with the label the Grafana sidecar watches.
kubectl -n monitoring create configmap carequeue-grafana-dashboard \
  --from-file=carequeue.json="${ROOT}/monitoring/grafana-dashboard-carequeue.json" \
  --dry-run=client -o yaml \
  | kubectl label --local -f - grafana_dashboard=1 app.kubernetes.io/part-of=carequeue -o yaml \
  | kubectl annotate --local -f - grafana_folder=CareQueue -o yaml \
  | kubectl apply -f -

kubectl -n monitoring get pods
echo "Prometheus: kubectl -n monitoring port-forward svc/kps-prometheus 9090:9090"
echo "Grafana:    kubectl -n monitoring port-forward svc/kps-grafana 3001:80   (user admin)"
echo "Password:   kubectl -n monitoring get secret kps-grafana -o jsonpath='{.data.admin-password}' | base64 -d"
