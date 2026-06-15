<template>
  <Teleport to="body">
    <div v-if="open" class="drawer-layer" @click.self="emit('close')">
      <aside
        ref="panelRef"
        class="drawer"
        :class="{ wide: width === 'wide' }"
        :aria-label="label"
        role="dialog"
        aria-modal="true"
      >
        <header class="drawer-header">
          <div>
            <p v-if="kicker" class="page-kicker">{{ kicker }}</p>
            <h2>{{ title }}</h2>
          </div>
          <slot name="header-actions" />
        </header>
        <div class="drawer-body">
          <slot />
        </div>
      </aside>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { nextTick, onBeforeUnmount, ref, watch } from "vue";

const props = withDefaults(defineProps<{
  open: boolean;
  label: string;
  title: string;
  kicker?: string;
  width?: "default" | "wide";
}>(), {
  kicker: "",
  width: "default",
});

const emit = defineEmits<{
  close: [];
}>();

const panelRef = ref<HTMLElement | null>(null);
let previousFocus: HTMLElement | null = null;

function focusableNodes(): HTMLElement[] {
  if (!panelRef.value) return [];
  return Array.from(
    panelRef.value.querySelectorAll<HTMLElement>(
      'button:not([disabled]), [href], input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
    ),
  ).filter((node) => !node.hasAttribute("hidden") && node.offsetParent !== null);
}

function trapFocus(event: KeyboardEvent) {
  if (!props.open || event.key !== "Tab") return;
  const nodes = focusableNodes();
  if (nodes.length === 0) {
    event.preventDefault();
    panelRef.value?.focus();
    return;
  }
  const first = nodes[0];
  const last = nodes[nodes.length - 1];
  const active = document.activeElement;
  if (event.shiftKey && active === first) {
    event.preventDefault();
    last.focus();
  } else if (!event.shiftKey && active === last) {
    event.preventDefault();
    first.focus();
  }
}

function handleKeydown(event: KeyboardEvent) {
  if (!props.open) return;
  if (event.key === "Escape") {
    event.preventDefault();
    emit("close");
    return;
  }
  trapFocus(event);
}

async function focusDrawer() {
  await nextTick();
  const nodes = focusableNodes();
  const autofocusNode = nodes.find((node) => node.hasAttribute("autofocus"));
  (autofocusNode ?? nodes[0] ?? panelRef.value)?.focus();
}

watch(
  () => props.open,
  async (open) => {
    if (open) {
      previousFocus = document.activeElement instanceof HTMLElement ? document.activeElement : null;
      document.addEventListener("keydown", handleKeydown);
      await focusDrawer();
      return;
    }
    document.removeEventListener("keydown", handleKeydown);
    previousFocus?.focus();
  },
  { immediate: true },
);

onBeforeUnmount(() => {
  document.removeEventListener("keydown", handleKeydown);
});
</script>

<style scoped>
.drawer-layer {
  position: fixed;
  inset: 0;
  z-index: 60;
  display: flex;
  justify-content: flex-end;
  background: oklch(18% 0.017 248 / 36%);
}

.drawer {
  display: grid;
  width: min(460px, 100%);
  grid-template-rows: auto minmax(0, 1fr);
  border-left: 1px solid var(--color-border);
  background: var(--color-surface);
  box-shadow: var(--shadow-popover);
  outline: none;
}

.drawer.wide {
  width: min(640px, 100%);
}

.drawer-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  border-bottom: 1px solid var(--color-border);
  padding: 14px 16px;
}

.drawer-header h2 {
  margin: 0;
  font-size: 16px;
  font-weight: 760;
  line-height: 1.2;
}

.drawer-body {
  overflow: auto;
  min-height: 0;
}

@media (max-width: 920px) {
  .drawer,
  .drawer.wide {
    width: 100%;
  }
}
</style>
