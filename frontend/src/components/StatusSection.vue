<script setup>
defineProps({
  text: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['cancel'])
</script>

<template>
  <section>
    <div class="status-card" tabindex="-1">
      <div class="spinner"></div>
      <p class="status-text" aria-live="polite" aria-atomic="true">{{ text }}</p>
      <button class="btn btn-secondary" @click="emit('cancel')">Cancel</button>
    </div>
  </section>
</template>
