<script setup>
import ReceiptCard from './ReceiptCard.vue'

defineProps({
  jobs: {
    type: Array,
    required: true,
  },
})

const emit = defineEmits(['scan-more'])
</script>

<template>
  <section>
    <div tabindex="-1">
      <ReceiptCard
        v-for="(job, i) in jobs"
        :key="job.jobId || i"
        :job="job"
        :show-actions="false"
      />
    </div>
    <button class="btn btn-primary" style="margin-top:1.25rem" @click="emit('scan-more')">
      Scan more receipts
    </button>
  </section>
</template>
