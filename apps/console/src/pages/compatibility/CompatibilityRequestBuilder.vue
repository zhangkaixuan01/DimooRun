<template>
  <section class="panel builder-panel">
    <header class="panel-header">
      <div>
        <p class="section-kicker">Runtime explorer</p>
        <h2 class="panel-title">LangGraph compatibility request builder</h2>
      </div>
    </header>

    <div class="builder-grid">
      <form class="workflow-panel" @submit.prevent="$emit('createAssistant')">
        <h3>Create assistant</h3>
        <label>
          <span>Name</span>
          <input :value="assistantName" class="input" @input="$emit('update:assistantName', eventValue($event))" />
        </label>
        <button class="button primary" type="submit" :disabled="busy">Create assistant</button>
      </form>

      <form class="workflow-panel" @submit.prevent="$emit('createThread')">
        <h3>Create thread</h3>
        <label>
          <span>Metadata label</span>
          <input :value="threadLabel" class="input" @input="$emit('update:threadLabel', eventValue($event))" />
        </label>
        <button class="button primary" type="submit" :disabled="busy">Create thread</button>
      </form>

      <form class="workflow-panel" @submit.prevent="$emit('createRun')">
        <h3>Create run</h3>
        <label>
          <span>Assistant ID</span>
          <input :value="assistantId" class="input" @input="$emit('update:assistantId', eventValue($event))" />
        </label>
        <label>
          <span>Thread ID</span>
          <input :value="threadId" class="input" @input="$emit('update:threadId', eventValue($event))" />
        </label>
        <label>
          <span>Input message</span>
          <input :value="inputMessage" class="input" @input="$emit('update:inputMessage', eventValue($event))" />
        </label>
        <div class="action-row">
          <button class="button primary" type="submit" :disabled="busy || !assistantId || !threadId">Create run</button>
          <button class="button" type="button" :disabled="busy || !assistantId || !threadId" @click="$emit('probeStream')">Stream probe</button>
        </div>
      </form>

      <section class="workflow-panel">
        <h3>Run controls</h3>
        <label>
          <span>Run ID</span>
          <input :value="runId" class="input" @input="$emit('update:runId', eventValue($event))" />
        </label>
        <div class="action-row">
          <button class="button" type="button" :disabled="busy || !threadId || !runId" @click="$emit('joinRun')">Join run</button>
          <button class="button danger" type="button" :disabled="busy || !threadId || !runId" @click="$emit('cancelRun')">Cancel run</button>
        </div>
      </section>
    </div>
  </section>
</template>

<script setup lang="ts">
defineProps<{
  assistantName: string;
  threadLabel: string;
  assistantId: string;
  threadId: string;
  runId: string;
  inputMessage: string;
  busy: boolean;
}>();

defineEmits<{
  (event: "update:assistantName", value: string): void;
  (event: "update:threadLabel", value: string): void;
  (event: "update:assistantId", value: string): void;
  (event: "update:threadId", value: string): void;
  (event: "update:runId", value: string): void;
  (event: "update:inputMessage", value: string): void;
  (event: "createAssistant"): void;
  (event: "createThread"): void;
  (event: "createRun"): void;
  (event: "probeStream"): void;
  (event: "joinRun"): void;
  (event: "cancelRun"): void;
}>();

function eventValue(event: Event): string {
  const target = event.target;
  return target instanceof HTMLInputElement ? target.value : "";
}
</script>

<style scoped>
.builder-panel,
.builder-grid {
  display: grid;
  gap: 16px;
}

.builder-grid {
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
}

.workflow-panel {
  display: grid;
  gap: 12px;
  border: 1px solid var(--color-border);
  border-radius: 8px;
  padding: 16px;
  background: var(--color-surface-muted);
}

.section-kicker {
  color: var(--color-text-muted);
  font-size: 0.78rem;
  font-weight: 800;
  margin: 0 0 4px;
  text-transform: uppercase;
}

h3 {
  margin: 0;
  font-size: 1rem;
}

label {
  display: grid;
  gap: 6px;
}

label span {
  color: var(--color-text-muted);
  font-size: 0.82rem;
  font-weight: 700;
}

.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
</style>
