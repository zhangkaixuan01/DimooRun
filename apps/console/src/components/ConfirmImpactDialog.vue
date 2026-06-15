<template>
  <div v-if="open" class="dialog-backdrop" role="presentation" @click.self="$emit('cancel')">
    <section class="dialog" role="dialog" aria-modal="true" :aria-label="title">
      <div class="dialog-header">
        <p class="dialog-kicker">{{ t("highRiskOperation") }}</p>
        <h2>{{ title }}</h2>
      </div>
      <dl class="impact-grid">
        <div>
          <dt>{{ t("deployment") }}</dt>
          <dd>{{ impactTarget }}</dd>
        </div>
        <div>
          <dt>{{ t("environment") }}</dt>
          <dd>{{ environment }}</dd>
        </div>
        <div>
          <dt>{{ t("affectsNewRuns") }}</dt>
          <dd>{{ affectsNewRuns ? "yes" : "no" }}</dd>
        </div>
        <div>
          <dt>{{ t("affectsExistingRuns") }}</dt>
          <dd>{{ affectsExistingRuns ? "yes" : "no" }}</dd>
        </div>
        <div>
          <dt>AuditLog</dt>
          <dd>{{ writesAuditLog ? "yes" : "no" }}</dd>
        </div>
        <div>
          <dt>{{ t("rollbackable") }}</dt>
          <dd>{{ rollbackable ? "yes" : "no" }}</dd>
        </div>
      </dl>
      <p class="audit">{{ t("auditLogNotice") }}</p>
      <div class="dialog-actions">
        <button class="button" type="button" @click="$emit('cancel')">{{ t("cancel") }}</button>
        <button class="button danger" type="button" @click="$emit('confirm')">{{ t("confirm") }}</button>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { useI18n } from "../i18n/useI18n";

defineProps<{
  open: boolean;
  title: string;
  impactTarget: string;
  environment: string;
  affectsNewRuns: boolean;
  affectsExistingRuns: boolean;
  writesAuditLog: boolean;
  rollbackable: boolean;
}>();

defineEmits<{
  confirm: [];
  cancel: [];
}>();

const { t } = useI18n();
</script>

<style scoped>
.dialog-backdrop {
  position: fixed;
  inset: 0;
  z-index: 40;
  display: grid;
  place-items: center;
  background: rgb(0 0 0 / 42%);
  padding: 18px;
}

.dialog {
  width: min(560px, 100%);
  border: 1px solid var(--color-border);
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-popover);
}

.dialog-header {
  border-bottom: 1px solid var(--color-border);
  padding: 14px 16px;
}

.dialog-kicker {
  margin: 0 0 6px;
  color: var(--color-danger);
  font-size: 12px;
  font-weight: 800;
  text-transform: uppercase;
}

h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 760;
}

.impact-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 10px;
  margin: 0;
  padding: 14px 16px;
}

.impact-grid div {
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  padding: 10px;
}

dt {
  color: var(--color-text-muted);
  font-size: 12px;
}

dd {
  margin: 4px 0 0;
  font-weight: 700;
}

.audit {
  margin: 0 16px 16px;
  color: var(--color-text-muted);
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  border-top: 1px solid var(--color-border);
  padding: 14px 16px;
}
</style>
