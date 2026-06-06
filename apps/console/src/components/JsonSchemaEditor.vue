<template>
  <label class="json-schema-editor">
    <span>{{ label }}</span>
    <textarea
      class="textarea code-input"
      :rows="rows"
      :value="modelValue"
      @input="$emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
    ></textarea>
    <small v-if="error" class="json-schema-editor__error">
      {{ error.message }} ({{ error.line }}:{{ error.column }})
    </small>
  </label>
</template>

<script setup lang="ts">
import type { JsonParseFailure } from "../forms/jsonForm";

withDefaults(defineProps<{
  label: string;
  modelValue: string;
  error?: JsonParseFailure | null;
  rows?: number;
}>(), {
  error: null,
  rows: 10,
});

defineEmits<{
  "update:modelValue": [value: string];
}>();
</script>

<style scoped>
.json-schema-editor {
  display: grid;
  gap: 6px;
}

.json-schema-editor__error {
  color: var(--color-danger);
  font-weight: 700;
}
</style>
