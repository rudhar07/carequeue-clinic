#!/bin/sh
# Generate steady API traffic so the Grafana panels (request rate, latency,
# error rate) have something to show. Mostly reads, plus some 404s and 422s.
#
#   scripts/load-test.sh                                   # 60 s against localhost:3000
#   BASE_URL=http://carequeue.local/api DURATION=120 CONCURRENCY=8 scripts/load-test.sh
#
# Kubernetes (kind, scripts/kind-up.sh): drive the backend HPA through the Ingress
#   BASE_URL=http://localhost:8088/api HOST_HEADER=carequeue.local \
#     DURATION=180 CONCURRENCY=24 scripts/load-test.sh
#   kubectl get hpa -n carequeue -w            # in another terminal
set -eu

BASE_URL="${BASE_URL:-http://localhost:3000/api}"
DURATION="${DURATION:-60}"
CONCURRENCY="${CONCURRENCY:-4}"
HOST_HEADER="${HOST_HEADER:-}"   # e.g. carequeue.local, to use the Ingress host rule

PATHS="/doctors /patients /stats/today /queue?doctor_id=1 /doctors/1/slots?date=$(date +%F) /appointments /patients?q=Sharma /doctors/9999 /queue"

worker() {
  end=$(( $(date +%s) + DURATION ))
  count=0
  while [ "$(date +%s)" -lt "$end" ]; do
    for p in $PATHS; do
      if [ -n "$HOST_HEADER" ]; then
        curl -s -o /dev/null -H "Host: $HOST_HEADER" "$BASE_URL$p" || true
      else
        curl -s -o /dev/null "$BASE_URL$p" || true
      fi
      count=$((count + 1))
    done
  done
  echo "worker $1: $count requests"
}

echo "Load test: $CONCURRENCY workers x ${DURATION}s against $BASE_URL${HOST_HEADER:+ (Host: $HOST_HEADER)}"
i=1
while [ "$i" -le "$CONCURRENCY" ]; do
  worker "$i" &
  i=$((i + 1))
done
wait
echo "done"
