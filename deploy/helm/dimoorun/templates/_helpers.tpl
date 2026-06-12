{{- define "dimoorun.fullname" -}}
{{- default .Chart.Name .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "dimoorun.labels" -}}
app.kubernetes.io/name: {{ include "dimoorun.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
helm.sh/chart: {{ .Chart.Name }}-{{ .Chart.Version | replace "+" "_" }}
{{- end -}}

{{- define "dimoorun.selectorLabels" -}}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "dimoorun.serverLabels" -}}
{{ include "dimoorun.selectorLabels" . }}
app.kubernetes.io/component: server
{{- end -}}

{{- define "dimoorun.workerLabels" -}}
{{ include "dimoorun.selectorLabels" . }}
app.kubernetes.io/component: worker
{{- end -}}

{{- define "dimoorun.consoleLabels" -}}
{{ include "dimoorun.selectorLabels" . }}
app.kubernetes.io/component: console
{{- end -}}
