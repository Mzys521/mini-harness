<script setup lang="ts">
import { useToastStore } from "@/stores/toast";

const toasts = useToastStore();
</script>

<template>
  <div class="toast-stack" aria-live="polite" role="status">
    <div v-for="message in toasts.messages" :key="message.id" class="toast">{{ message.text }}</div>
  </div>
</template>
