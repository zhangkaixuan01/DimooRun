<template>
  <RouterView v-if="route.meta.public" />
  <AppShell v-else />
</template>

<script setup lang="ts">
import { useRoute } from "vue-router";

import AppShell from "./layouts/AppShell.vue";

const route = useRoute();
</script>
