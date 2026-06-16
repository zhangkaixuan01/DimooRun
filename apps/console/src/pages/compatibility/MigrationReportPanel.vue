<template>
  <section class="panel report-panel">
    <header class="panel-header">
      <div>
        <p class="section-kicker">{{ t("migrationReport") }}</p>
        <h2 class="panel-title">{{ t("compatibilityMigrationGuidance") }}</h2>
      </div>
      <span class="status-chip" :data-status="report?.overallStatus || 'unknown'">
        {{ report?.overallStatus || "unknown" }}
      </span>
    </header>

    <div v-if="report" class="report-grid">
      <div>
        <span class="report-label">{{ t("adapterContract") }}</span>
        <strong>{{ report.adapterContractVersion }}</strong>
      </div>
      <div>
        <span class="report-label">{{ t("framework") }}</span>
        <strong>{{ report.framework }} / {{ report.adapter }}</strong>
      </div>
      <div>
        <span class="report-label">{{ t("checkpointMode") }}</span>
        <strong>{{ String(report.checkpointRequirements.mode || "optional") }}</strong>
      </div>
      <div>
        <span class="report-label">{{ t("blockedReason") }}</span>
        <strong>{{ report.blockedReason || "none" }}</strong>
      </div>
    </div>

    <div v-if="report" class="report-columns">
      <div>
        <h3>{{ t("requiredConfig") }}</h3>
        <ul>
          <li v-for="item in report.requiredDimooRunConfig" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div>
        <h3>{{ t("unsupportedCapability") }}</h3>
        <ul v-if="report.unsupportedCapabilities.length > 0">
          <li v-for="item in report.unsupportedCapabilities" :key="String(item.capability)">
            {{ item.capability }}: {{ item.reason }}
          </li>
        </ul>
        <p v-else class="muted">{{ t("noUnsupportedCapability") }}</p>
      </div>
      <div>
        <h3>{{ t("governanceImplications") }}</h3>
        <ul>
          <li v-for="item in report.governanceImplications" :key="item">{{ item }}</li>
        </ul>
      </div>
      <div>
        <h3>{{ t("recommendedActions") }}</h3>
        <ul>
          <li v-for="item in report.recommendedActions" :key="item">{{ item }}</li>
        </ul>
      </div>
    </div>

    <div v-if="report && report.remediationSteps.length > 0" class="remediation-block">
      <h3>Recommended remediation</h3>
      <div
        v-for="step in report.remediationSteps"
        :key="String(step.capability)"
        class="remediation-card"
      >
        <div class="report-grid">
          <div>
            <span class="report-label">Capability</span>
            <strong>{{ String(step.capability || "") }}</strong>
          </div>
          <div>
            <span class="report-label">Severity</span>
            <strong>{{ String(step.severity || "") }}</strong>
          </div>
          <div class="remediation-span">
            <span class="report-label">Target files</span>
            <strong>{{ joinValues(step.target_files) }}</strong>
          </div>
          <div class="remediation-span">
            <span class="report-label">Recommended action</span>
            <strong>{{ String(step.recommended_action || "") }}</strong>
          </div>
          <div class="remediation-span">
            <span class="report-label">Verification command</span>
            <code>{{ String(step.verification_command || "") }}</code>
          </div>
          <div>
            <span class="report-label">Native route</span>
            <RouterLink :to="String(step.native_route || '/compatibility')">
              {{ String(step.native_route || "") }}
            </RouterLink>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>

<script setup lang="ts">
import { RouterLink } from "vue-router";

import type { CompatibilityMigrationReport } from "../../api/types";
import { useI18n } from "../../i18n/useI18n";

defineProps<{
  report: CompatibilityMigrationReport | null;
}>();

const { t } = useI18n();

function joinValues(value: unknown): string {
  return Array.isArray(value) ? value.map((item) => String(item)).join(", ") : "";
}
</script>

<style scoped>
.report-panel {
  display: grid;
  gap: 16px;
}

.report-grid {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.report-columns {
  display: grid;
  gap: 16px;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
}

.report-label,
.section-kicker {
  color: var(--color-text-muted);
  display: block;
  font-size: 0.78rem;
  font-weight: 600;
  margin-bottom: 4px;
  text-transform: uppercase;
}

.status-chip {
  align-self: start;
  border: 1px solid var(--color-border);
  border-radius: 999px;
  padding: 6px 10px;
  text-transform: uppercase;
  font-size: 0.78rem;
  font-weight: 600;
}

.status-chip[data-status="compatible"] {
  color: var(--color-success);
}

.status-chip[data-status="migration_required"] {
  color: var(--color-warning);
}

.status-chip[data-status="blocked"] {
  color: var(--color-danger);
}

h3 {
  margin: 0 0 8px;
  font-size: 0.96rem;
}

ul {
  margin: 0;
  padding-left: 18px;
}

li {
  margin-bottom: 6px;
}

.remediation-block {
  display: grid;
  gap: 12px;
}

.remediation-card {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: var(--color-surface-muted);
  padding: 12px;
}

.remediation-span {
  grid-column: 1 / -1;
}

code {
  overflow-wrap: anywhere;
}
</style>
