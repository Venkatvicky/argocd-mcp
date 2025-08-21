{{/* Return the fully qualified app name */}}
{{- define "argocd-mcp-server.fullname" -}}
{{- printf "%s-%s" .Release.Name .Chart.Name | trunc 63 | trimSuffix "-" -}}
{{- end }}

{{/* Short chart name */}}
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
