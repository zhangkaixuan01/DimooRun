<script setup lang="ts">
import DeploymentsPage from "./DeploymentsPage.vue";

defineProps<{
  deploymentId: string;
}>();
</script>

<template>
  <DeploymentsPage :initial-deployment-id="deploymentId" />
</template>
