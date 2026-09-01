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
    receipts.value = (data.receipts || []).slice().sort((a, b) => {
      const da = a.receiptDate || ''
      const db = b.receiptDate || ''
      if (db < da) return -1
      if (db > da) return 1
      return 0
    })
  } catch (err) {
    console.error('History load error:', err)
  }
}

onMounted(loadHistory)

function onEdit(job) {
  editingJob.value = job
}

function onDeleted(jobId) {
  receipts.value = receipts.value.filter(r => r.jobId !== jobId)
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
      @deleted="onDeleted"
    />

    <EditModal
      v-if="editingJob"
      :job="editingJob"
      @close="onCloseModal"
      @saved="onSaved"
    />
  </section>
</template>
