<template>
  <RouterLink class="resource-link" :to="to"><slot /></RouterLink>
</template>

<script setup lang="ts">
defineProps<{ to: string }>();
</script>

<style scoped>
.resource-link {
  color: var(--color-accent);
  font-weight: 700;
  text-decoration: none;
}

.resource-link:hover {
  text-decoration: underline;
}
</style>
