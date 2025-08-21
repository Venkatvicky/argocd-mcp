{{/* Chart short name */}}
{{- define "argocd-mcp-server.name" -}}
{{- .Chart.Name -}}
{{- end }}

{{/* Common labels */}}
{{- define "argocd-mcp-server.labels" -}}
app.kubernetes.io/name: {{ include "argocd-mcp-server.name" . }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}
