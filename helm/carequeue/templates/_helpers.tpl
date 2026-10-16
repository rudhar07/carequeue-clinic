{{/* Chart name. */}}
{{- define "carequeue.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Fully qualified app name. Release "carequeue" -> "carequeue" (not "carequeue-carequeue"),
so the Services are carequeue-backend, carequeue-frontend, carequeue-postgresql.
*/}}
{{- define "carequeue.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "carequeue.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/* Common labels on every object. */}}
{{- define "carequeue.labels" -}}
helm.sh/chart: {{ include "carequeue.chart" . }}
app.kubernetes.io/name: {{ include "carequeue.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: carequeue
{{- end -}}

{{/*
Selector labels of one component (immutable once a Deployment exists):
  include "carequeue.selectorLabels" (dict "ctx" $ "component" "backend")
*/}}
{{- define "carequeue.selectorLabels" -}}
app.kubernetes.io/name: {{ include "carequeue.name" .ctx }}
app.kubernetes.io/instance: {{ .ctx.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Labels for one component = common labels + selector labels. */}}
{{- define "carequeue.componentLabels" -}}
{{ include "carequeue.labels" .ctx }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* Object names */}}
{{- define "carequeue.backend.fullname" -}}{{ include "carequeue.fullname" . }}-backend{{- end -}}
{{- define "carequeue.frontend.fullname" -}}{{ include "carequeue.fullname" . }}-frontend{{- end -}}
{{- define "carequeue.postgresql.fullname" -}}{{ include "carequeue.fullname" . }}-postgresql{{- end -}}
{{- define "carequeue.configName" -}}{{ include "carequeue.fullname" . }}-config{{- end -}}

{{- define "carequeue.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "carequeue.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{/* Images: an empty tag falls back to the chart's appVersion. */}}
{{- define "carequeue.backend.image" -}}
{{- printf "%s:%s" .Values.backend.image.repository (.Values.backend.image.tag | default .Chart.AppVersion | toString) -}}
{{- end -}}
{{- define "carequeue.frontend.image" -}}
{{- printf "%s:%s" .Values.frontend.image.repository (.Values.frontend.image.tag | default .Chart.AppVersion | toString) -}}
{{- end -}}
{{- define "carequeue.postgresql.image" -}}
{{- printf "%s:%s" .Values.postgresql.image.repository (.Values.postgresql.image.tag | toString) -}}
{{- end -}}

{{/* GIT_SHA shown by /api/info: explicit value, else the backend image tag, else appVersion. */}}
{{- define "carequeue.gitSha" -}}
{{- .Values.backend.env.GIT_SHA | default .Values.backend.image.tag | default .Chart.AppVersion | toString -}}
{{- end -}}

{{/* Secret holding DATABASE_URL (+ POSTGRES_USER/PASSWORD for the in-chart database). */}}
{{- define "carequeue.dbSecretName" -}}
{{- default (printf "%s-db" (include "carequeue.fullname" .)) .Values.database.existingSecret -}}
{{- end -}}

{{/* Database host: explicit host, else the in-chart PostgreSQL Service. */}}
{{- define "carequeue.dbHost" -}}
{{- if .Values.database.host -}}
{{- .Values.database.host -}}
{{- else if .Values.postgresql.enabled -}}
{{- include "carequeue.postgresql.fullname" . -}}
{{- else -}}
{{- fail "database.host is required when postgresql.enabled=false (e.g. the RDS endpoint)" -}}
{{- end -}}
{{- end -}}

{{/* Pod-level securityContext (Pod Security "restricted" compliant). */}}
{{- define "carequeue.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .uid }}
fsGroup: {{ .uid }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{/* Container-level securityContext shared by every container. */}}
{{- define "carequeue.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
privileged: false
capabilities:
  drop: ["ALL"]
{{- end -}}

{{/*
initContainer: wait until the database accepts TCP connections (max ~3 minutes).
Uses the backend image itself (Python), so no extra image is pulled and it
also works for an external database (RDS).
*/}}
{{- define "carequeue.waitForDb" -}}
- name: wait-for-db
  image: {{ include "carequeue.backend.image" . | quote }}
  imagePullPolicy: {{ .Values.backend.image.pullPolicy }}
  command:
    - python
    - -c
    - |
      import os, socket, sys, time
      host, port = os.environ["DB_HOST"], int(os.environ["DB_PORT"])
      for attempt in range(1, 91):
          try:
              socket.create_connection((host, port), timeout=2).close()
              print(f"database {host}:{port} is reachable", flush=True)
              sys.exit(0)
          except OSError as err:
              print(f"waiting for database {host}:{port} ({attempt}/90): {err}", flush=True)
              time.sleep(2)
      sys.exit(f"database {host}:{port} not reachable")
  envFrom:
    - configMapRef:
        name: {{ include "carequeue.configName" . }}
  securityContext:
    {{- include "carequeue.containerSecurityContext" . | nindent 4 }}
  resources:
    requests: {cpu: 10m, memory: 32Mi}
    limits: {cpu: 100m, memory: 64Mi}
{{- end -}}

{{/*
Replica count for a Deployment:
  include "carequeue.replicas" (dict "ctx" $ "name" <deployment name> "cfg" .Values.backend)
With the HPA on, keep the count the HPA has already set, so a "helm upgrade"
does not reset a scaled-out Deployment back to replicaCount. lookup returns
nothing in "helm template"/dry-run, which then falls back to replicaCount
(never below autoscaling.minReplicas).
*/}}
{{- define "carequeue.replicas" -}}
{{- $replicas := int .cfg.replicaCount -}}
{{- if .cfg.autoscaling.enabled -}}
{{- $replicas = max $replicas (int .cfg.autoscaling.minReplicas) | int -}}
{{- $live := lookup "apps/v1" "Deployment" .ctx.Release.Namespace .name -}}
{{- if $live -}}
{{- if $live.spec.replicas -}}
{{- $replicas = max $replicas (int $live.spec.replicas) | int -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- $replicas -}}
{{- end -}}
