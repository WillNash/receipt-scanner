<script setup>
import { ref, onMounted, inject } from 'vue'
import ReceiptCard from './ReceiptCard.vue'
import EditModal from './EditModal.vue'

const emit = defineEmits(['saved'])

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')

const receipts = ref([])
const editingJob = ref(null)

async function loadHistory() {
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/receipts`)
    if (!resp.ok) return
    const data = await resp.json()
    receipts.value = data.receipts || []
  } catch (err) {
    console.error('History load error:', err)
  }
}

onMounted(loadHistory)

function onEdit(job) {
  editingJob.value = job
}

async function onSaved() {
  editingJob.value = null
  await loadHistory()
  emit('saved')
}

function onCloseModal() {
  editingJob.value = null
}
</script>

<template>
  <section v-if="receipts.length > 0">
    <h2 class="section-title">Recent receipts</h2>
    <ReceiptCard
      v-for="job in receipts"
      :key="job.jobId"
      :job="job"
      :show-actions="true"
      @edit="onEdit"
    />

    <EditModal
      v-if="editingJob"
      :job="editingJob"
      @close="onCloseModal"
      @saved="onSaved"
    />
  </section>
</template>
