<template>
  <Teleport to="body">
    <div v-if="open" class="confirm-layer" @click.self="$emit('cancel')">
      <section class="confirm-dialog" role="alertdialog" aria-modal="true" :aria-labelledby="titleId">
        <header class="confirm-header">
          <div>
            <p class="page-kicker">{{ kicker }}</p>
            <h2 :id="titleId">{{ title }}</h2>
          </div>
        </header>
        <div class="confirm-body">
          <p>{{ message }}</p>
          <dl v-if="items.length > 0" class="impact-list">
            <template v-for="item in items" :key="item.label">
              <dt>{{ item.label }}</dt>
              <dd>{{ item.value }}</dd>
            </template>
          </dl>
          <p v-if="warning" class="warning">{{ warning }}</p>
          <section v-if="error" class="confirm-error">
            <strong>{{ error.errorCode }}</strong>
            <span>{{ error.message }}</span>
            <small v-if="error.requestId" class="mono">request_id={{ error.requestId }}</small>
          </section>
        </div>
        <footer class="confirm-actions">
          <button class="button" type="button" @click="$emit('cancel')">{{ cancelLabel }}</button>
          <button class="button danger" type="button" :disabled="busy" @click="$emit('confirm')">
            {{ busy ? busyLabel : confirmLabel }}
          </button>
        </footer>
      </section>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import type { ConsoleApiError } from "../api/client";

const titleId = `danger-confirm-${Math.random().toString(36).slice(2)}`;

withDefaults(defineProps<{
  open: boolean;
  title: string;
  message: string;
  items?: Array<{ label: string; value: string }>;
  warning?: string;
  kicker?: string;
  confirmLabel?: string;
  cancelLabel?: string;
  busyLabel?: string;
  busy?: boolean;
  error?: ConsoleApiError | null;
}>(), {
  items: () => [],
  warning: "",
  kicker: "Danger Zone",
  confirmLabel: "确认",
  cancelLabel: "取消",
  busyLabel: "处理中",
  busy: false,
  error: null,
});

defineEmits<{
  confirm: [];
  cancel: [];
}>();
</script>

<style scoped>
.confirm-layer {
  position: fixed;
  inset: 0;
  z-index: 90;
  display: grid;
  place-items: center;
  background: oklch(18% 0.017 248 / 42%);
  padding: 18px;
}

.confirm-dialog {
  display: grid;
  width: min(440px, 100%);
  overflow: hidden;
  border: 1px solid color-mix(in srgb, var(--color-danger) 55%, var(--color-border));
  border-radius: var(--radius-md);
  background: var(--color-surface);
  box-shadow: var(--shadow-popover);
}

.confirm-header,
.confirm-body,
.confirm-actions {
  padding: 16px;
}

.confirm-header {
  border-bottom: 1px solid var(--color-border);
}

.confirm-header h2 {
  margin: 0;
  font-size: 19px;
}

.confirm-body {
  display: grid;
  gap: 12px;
}

.confirm-body p {
  margin: 0;
}

.impact-list {
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 7px 12px;
  margin: 0;
  border: 1px solid var(--color-border);
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-surface-muted) 46%, transparent);
  padding: 10px;
}

.impact-list dt {
  color: var(--color-text-muted);
  font-size: 12px;
  font-weight: 800;
}

.impact-list dd {
  margin: 0;
  overflow-wrap: anywhere;
}

.warning {
  color: var(--color-danger);
  font-weight: 800;
}

.confirm-error {
  display: grid;
  gap: 5px;
  border: 1px solid color-mix(in srgb, var(--color-danger) 68%, var(--color-border));
  border-radius: var(--radius-sm);
  background: color-mix(in srgb, var(--color-danger-soft) 56%, var(--color-surface));
  padding: 10px;
}

.confirm-error span,
.confirm-error small {
  color: var(--color-text-muted);
}

.confirm-actions {
  display: flex;
  justify-content: flex-end;
  gap: 8px;
  border-top: 1px solid var(--color-border);
}
</style>
