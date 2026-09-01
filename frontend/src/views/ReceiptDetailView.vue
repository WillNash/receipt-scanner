<script setup>
import { ref, inject, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import ReceiptCard from '../components/ReceiptCard.vue'
import EditModal from '../components/EditModal.vue'
import { useReceipts } from '../composables/useReceipts.js'

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')
const route = useRoute()
const router = useRouter()

const { updateReceipt, removeReceipt } = useReceipts(apiFetch, CONFIG)

const job = ref(null)
const loading = ref(true)
const error = ref(null)
const editingJob = ref(null)

async function loadJob() {
  loading.value = true
  error.value = null
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/jobs/${route.params.jobId}`)
    if (!resp.ok) throw new Error('Failed to load receipt')
    job.value = await resp.json()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
}

onMounted(loadJob)

function onDeleted(jobId) {
  removeReceipt(jobId)
  router.push('/list')
}

async function onSaved() {
  editingJob.value = null
  await loadJob()
  if (job.value) updateReceipt(job.value.jobId, job.value)
}
</script>

<template>
  <div class="detail-view">
    <button class="btn btn-secondary back-btn" @click="router.push('/list')">← Back to list</button>

    <div v-if="loading" class="state-text">Loading receipt…</div>
    <div v-else-if="error" class="state-text state-text--error">{{ error }}</div>

    <template v-else-if="job">
      <ReceiptCard
        :job="job"
        :show-actions="true"
        @edit="editingJob = job"
        @deleted="onDeleted"
      />

      <EditModal
        v-if="editingJob"
        :job="editingJob"
        @close="editingJob = null"
        @saved="onSaved"
      />
    </template>
  </div>
</template>

<style scoped>
.detail-view {
  padding: 0.5rem 0;
}

.back-btn {
  margin-bottom: 1.25rem;
}

.state-text {
  text-align: center;
  padding: 3rem;
  color: var(--muted);
}

.state-text--error {
  color: var(--danger);
}
</style>
