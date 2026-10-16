# Troubleshooting lab

Six broken scenarios, each **actually run** on the kind cluster `cq` against
the live CareQueue release (namespace `carequeue`). Every case has its own
manifest or patch here and a full transcript (break, symptom, investigation,
fix, verification, clean-up) in `docs/evidence/ts-NN-*.txt`. The outputs quoted
below are copied from those transcripts.

| # | Scenario | Symptom | Files | Transcript |
|---|----------|---------|-------|------------|
| 1 | Wrong image tag | `ImagePullBackOff` | `01-broken-image.yaml` | `ts-01-image-pull-backoff.txt` |
| 2 | Wrong `DATABASE_URL` host | `Running` but `0/1` Ready, readiness 503 | `02-wrong-database-url.yaml`, `02-database-url.fix.patch.json` | `ts-02-wrong-database-url.txt` |
| 3 | Service selector mismatch | No endpoints, `/api` 503 (Ingress) / 502 (nginx) | `03-service-selector.patch.json`, `03-service-selector.fix.patch.json` | `ts-03-service-selector.txt` |
| 4 | Ingress points at a missing Service | 503 on `/api` only | `04-broken-ingress.yaml`, `04-ingress.fix.patch.json` | `ts-04-broken-ingress.txt` |
| 5 | HPA without CPU requests | `cpu: <unknown>/60%` | `05-hpa-no-requests.yaml`, `05-hpa.fix.patch.json` | `ts-05-hpa-unknown.txt` |
| 6 | Liveness probe on a wrong path | restart loop after a "green" rollout | `06-bad-liveness.values.yaml` (fix: `helm rollback`) | `ts-06-bad-liveness-helm-rollback.txt` |

Cases 1, 2, 4 and 5 add separate `cq-lab-*` objects next to the release, so the
real app keeps working. Cases 3 and 6 break the release itself (3 with
`kubectl patch`, 6 with a `helm upgrade`).

The general loop for all of them:

```bash
kubectl get pods,svc,endpointslices,ingress,hpa -n carequeue      # what is not Running / Ready / populated?
kubectl describe pod <pod> -n carequeue                           # Events at the bottom
kubectl get events -n carequeue --sort-by=.lastTimestamp
kubectl logs <pod> -n carequeue [-c <container>] [--previous]
helm history carequeue -n carequeue; helm get values carequeue -n carequeue
```

---

## Case 1: ImagePullBackOff (wrong image tag) <a id="case-1"></a>

**Break:** `kubectl apply -n carequeue -f troubleshooting/01-broken-image.yaml`
(a backend copy `cq-lab-image` using `carequeue-backend:1.0.1`).

**Symptom**
```
NAME                            READY   STATUS             RESTARTS   AGE
cq-lab-image-8647d4cb56-x65jx   0/1     ImagePullBackOff   0          15s
```

**Investigate**
```bash
kubectl describe pod -n carequeue -l app=cq-lab-image          # Events
kubectl get deployment cq-lab-image -n carequeue -o jsonpath='{.spec.template.spec.containers[0].image}'
docker exec cq-control-plane crictl images | grep carequeue     # what the kind node actually has
```
```
Failed to pull image "carequeue-backend:1.0.1": failed to pull and unpack image
"docker.io/library/carequeue-backend:1.0.1": failed to resolve reference ...: pull access denied,
repository does not exist or may require authorization
```
The node only has `docker.io/library/carequeue-backend:local`.

**Root cause:** the tag `1.0.1` was never built or loaded. With no registry
prefix the kubelet asks Docker Hub, which has no such repository.

**Fix:** use a tag that exists. On the spot:
`kubectl set image -n carequeue deployment/cq-lab-image backend=carequeue-backend:local`.
For good: fix the tag in Git (manifest or `backend.image.tag`). In CI the tag
is always the commit SHA that the docker job pushed, so this case cannot happen
there unless the push failed.

**Verify:** `rollout status` → `successfully rolled out`, the pod is `1/1 Running`
and `/ready` returns `{"status":"ready","database":"up"}`.

---

## Case 2: wrong DATABASE_URL → Running but never Ready <a id="case-2"></a>

**Break:** `kubectl apply -n carequeue -f troubleshooting/02-wrong-database-url.yaml`.
The password comes from the real Secret via `$(POSTGRES_PASSWORD)`, but the
host is `carequeue-postgres` instead of `carequeue-postgresql`.

**Symptom:** `cq-lab-db-...   0/1   Running   0   23s`, and `kubectl rollout status` times out.

**Investigate**
```bash
kubectl describe pod -n carequeue -l app=cq-lab-db     # "Readiness probe failed: HTTP probe failed with statuscode: 503"
kubectl exec -n carequeue deploy/cq-lab-db -- python -c "...urlopen('http://127.0.0.1:8000/ready')..."
#   503 {"status":"unavailable","database":"down"}
kubectl exec ... -- python -c "...print DATABASE_URL with the password masked..."
#   postgresql+psycopg://carequeue:***@carequeue-postgres:5432/carequeue
kubectl exec ... -- python -c "import socket;socket.getaddrinfo('carequeue-postgres',5432)"
#   socket.gaierror: [Errno -2] Name or service not known
kubectl get svc -n carequeue -l app.kubernetes.io/component=postgresql     # carequeue-postgresql
```

**Root cause:** a typo in the host name. DNS fails, `SELECT 1` in `/ready`
fails, `/ready` answers 503, so the readiness probe keeps the pod out of the
Service. Liveness (`/health`) never touches the database, so the kubelet does
**not** restart the pod. That is the intended split: a database outage should
take pods out of rotation, not crash-loop them.

**Fix:** `kubectl patch -n carequeue deployment cq-lab-db --type=json --patch-file troubleshooting/02-database-url.fix.patch.json`.
In the chart the URL is built in one place (`templates/secret.yaml` from
`database.host`, defaulting to the in-chart Service), which avoids this class of typo.

**Verify:** new pod `1/1 Running`, `/ready` → `{"status":"ready","database":"up"}`.

---

## Case 3: Service selector mismatch → no endpoints <a id="case-3"></a>

**Break:** someone edits the live, Helm-managed Service:
`kubectl patch -n carequeue svc carequeue-backend --type=json --patch-file troubleshooting/03-service-selector.patch.json`
(selector `app.kubernetes.io/component: api`).

**Symptom**
```
$ curl -i http://localhost:8088/api/info           -> HTTP/1.1 503 Service Temporarily Unavailable   (ingress-nginx)
$ curl http://localhost:8088/                       -> 200   (the frontend is fine)
$ wget http://127.0.0.1:8080/api/info (in a frontend pod) -> HTTP/1.1 502 Bad Gateway   (nginx proxy)
$ helm test carequeue -n carequeue --logs           -> Phase: Failed, "Failed to connect to carequeue-backend port 8000"
```

**Investigate**
```bash
kubectl get svc carequeue-backend -n carequeue -o wide          # SELECTOR ...component=api...
kubectl get endpointslices -n carequeue -l kubernetes.io/service-name=carequeue-backend   # ENDPOINTS <unset>
kubectl get pods -n carequeue -l app.kubernetes.io/component=api                         # No resources found
kubectl get pods -n carequeue --show-labels                                               # pods have component=backend
helm get manifest carequeue -n carequeue | kubectl diff -n carequeue -f -                 # drift vs. the release
#   -    app.kubernetes.io/component: api
#   +    app.kubernetes.io/component: backend
```

**Root cause:** a Service routes to Pods by label. No Pod matches
`component=api`, so the EndpointSlice is empty: no endpoints, no traffic. The
pods themselves are healthy, which is why `kubectl get pods` looks fine.

**Fix:** restore the selector
(`kubectl patch ... --patch-file troubleshooting/03-service-selector.fix.patch.json`),
or re-apply the chart. `helm get manifest | kubectl diff -f -` is the quick way
to find hand edits on Helm-managed objects.

**Verify:** the EndpointSlice lists both backend pod IPs again, `/api/info`
returns 200, `kubectl diff` reports no drift, and `helm test` → `Phase: Succeeded`.

---

## Case 4: Ingress backend Service name/port wrong → 503 <a id="case-4"></a>

**Break:** `kubectl apply -n carequeue -f troubleshooting/04-broken-ingress.yaml`
(host `lab.carequeue.local`, `/api` → Service `carequeue-api`, port 8000).

**Symptom:** `curl -H 'Host: lab.carequeue.local' http://localhost:8088/api/info`
→ `HTTP/1.1 503 Service Temporarily Unavailable`, while `/` on the same host is 200.

**Investigate**
```bash
kubectl describe ingress cq-lab-ingress -n carequeue
#   /api   carequeue-api:8000 (<error: services "carequeue-api" not found>)
#   /      carequeue-frontend:http (10.244.0.12:8080,10.244.0.11:8080)
kubectl get svc -n carequeue                                    # the real name is carequeue-backend, port "http"
kubectl logs -n ingress-nginx deploy/ingress-nginx-controller | grep carequeue-api
#   Error obtaining Endpoints for Service "carequeue/carequeue-api": no object matching key ...
```

**Root cause:** the Ingress is only configuration. The controller resolves each
path to a Service's endpoints, and a missing Service (or a wrong port) leaves
that path with no upstream, so ingress-nginx answers 503 for that path only.

**Fix:** `kubectl patch -n carequeue ingress cq-lab-ingress --type=json --patch-file troubleshooting/04-ingress.fix.patch.json`
(Service `carequeue-backend`, port name `http`). The chart refers to ports by
name, so a port number change in values cannot break the Ingress.

**Verify:** `describe ingress` shows backend pod IPs for `/api`, and the curl returns `HTTP/1.1 200 OK`.

---

## Case 5: HPA shows `<unknown>` <a id="case-5"></a>

**Break:** `kubectl apply -n carequeue -f troubleshooting/05-hpa-no-requests.yaml`
(a Deployment with no `resources`, plus a CPU-utilisation HPA).

**Symptom:** `cq-lab-hpa   Deployment/cq-lab-hpa   cpu: <unknown>/60%   1   3   1`

**Investigate**
```bash
kubectl describe hpa cq-lab-hpa -n carequeue
#   ScalingActive  False  FailedGetResourceMetric  ... failed to get cpu utilization:
#   missing request for cpu in container web of Pod cq-lab-hpa-...
kubectl get deployment cq-lab-hpa -n carequeue -o jsonpath='{.spec.template.spec.containers[0].resources}'   # {}
kubectl top pods -n carequeue -l app=cq-lab-hpa          # 9m 12Mi: metrics-server works
kubectl get apiservice v1beta1.metrics.k8s.io            # AVAILABLE True
```

**Root cause:** utilisation is `usage / request`. With no CPU request there is
nothing to divide by. (The other cause of `<unknown>` is no metrics-server at
all; then `kubectl top` fails too. The first event right after creation,
"no metrics returned from resource metrics API", is just the first scrape not
having happened yet.)

**Fix:** add requests and limits
(`kubectl patch ... --patch-file troubleshooting/05-hpa.fix.patch.json`). The
chart sets requests on every container for this reason.

**Verify:** `cpu: 0%/60%`, `ScalingActive True ValidMetricFound`.

---

## Case 6: liveness probe on a wrong path → restart loop, fixed with `helm rollback` <a id="case-6"></a>

**Break:** a values change for the real release:
```bash
helm upgrade carequeue helm/carequeue -n carequeue -f helm/carequeue/values-dev.yaml \
  -f troubleshooting/06-bad-liveness.values.yaml      # backend.probes.liveness.path=/healthz
```
Helm reports `STATUS: deployed, REVISION: 3`. The startup probe (`/health`)
and the readiness probe (`/ready`) still pass, so the rolling update completes.

**Symptom** (98 s later)
```
carequeue-backend-5995d78cfb-4v89n   1/1     Running   3 (7s ago)   98s
carequeue-backend-5995d78cfb-f759v   0/1     Running   3 (2s ago)   93s
```

**Investigate**
```bash
kubectl get events -n carequeue --field-selector reason=Unhealthy   # Liveness probe failed: HTTP probe failed with statuscode: 404
kubectl get events -n carequeue --field-selector reason=Killing     # Container backend failed liveness probe, will be restarted
kubectl get deploy carequeue-backend -n carequeue -o jsonpath='{...livenessProbe.httpGet.path}'   # /healthz
kubectl exec ... -- python -c "...GET /health and /healthz..."      # /health 200, /healthz 404
helm get values carequeue -n carequeue                              # probes.liveness.path: /healthz
helm history carequeue -n carequeue                                 # revision 3 is the change
```

**Root cause:** `/healthz` is the frontend's nginx health path; the backend
serves `/health`. The kubelet restarts each container after 3 failed liveness
checks (about 30 s). In this run the API still answered 200 because the two
pods were rarely down at the same time, but every restart drops in-flight
requests and the back-off keeps growing. A "successful" Helm upgrade is not
proof of a healthy release; `helm test`, the restart count and the alerts are.

**Fix:** `helm rollback carequeue 2 -n carequeue --wait` (back to the last good
revision), then fix the value in Git.

**Verify:** `REVISION 4 ... Rollback to 2`, new pods with `RESTARTS 0` 45 s
later, `liveness=/health`, `/api/info` 200, and `helm test` → `Phase: Succeeded`.

---

## Real incidents seen while building this (not staged)

- **Transient `ImagePullBackOff` in `monitoring`** while installing
  kube-prometheus-stack: `dial tcp: lookup cdn01.quay.io on 192.168.65.254:53: server misbehaving`
  (Docker Desktop's DNS). `kubectl describe pod` showed it was DNS, not a wrong
  tag; the kubelet's retry pulled the image a minute later and `helm --wait` finished.
- **ingress-nginx admission webhook** rejected a second copy of the chart in
  another namespace: `host "carequeue.local" and path "/api" is already defined in ingress carequeue/carequeue`
  (see `docs/evidence/k8s-00-chart-validation.txt`). Two Ingresses cannot claim the
  same host and path; give the second release another `ingress.host`.
- **First install**: the backend's `wait-for-db` initContainer logged
  `waiting for database carequeue-postgresql:5432 (n/90): Connection refused`
  17 times (about 34 s) while PostgreSQL initialised; the backend containers
  started only afterwards, with 0 restarts (`docs/evidence/k8s-06-security-and-metrics.txt`).
