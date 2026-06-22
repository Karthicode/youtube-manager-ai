{{/*
Common labels stamped on every resource.
"helm.sh/chart" lets you filter by chart; "app.kubernetes.io/managed-by" marks
these resources as Helm-owned so `helm uninstall` can clean them up.
*/}}
{{- define "youtube-manager.labels" -}}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
DATABASE_URL — constructed here once so every template that needs it
can just include this snippet rather than repeating the pattern.
The postgres password comes from the Secret, injected as POSTGRES_PASSWORD
by the deployment, then substituted here via K8s $(VAR) syntax.
*/}}
{{- define "youtube-manager.databaseUrl" -}}
postgresql://{{ .Values.postgres.user }}:$(POSTGRES_PASSWORD)@{{ .Values.postgres.host }}:5432/{{ .Values.postgres.database }}
{{- end }}
