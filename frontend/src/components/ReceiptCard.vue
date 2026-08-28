<script setup>
import { ref, computed, inject } from 'vue'
import { formatDate } from '../utils.js'
import OcrDebugPanel from './OcrDebugPanel.vue'

const props = defineProps({
  job: {
    type: Object,
    required: true,
  },
  showActions: {
    type: Boolean,
    default: false,
  },
})

const emit = defineEmits(['edit', 'deleted'])

const apiFetch = inject('apiFetch', null)
const CONFIG = inject('CONFIG', null)

const showDebug = ref(false)

// URLs may be absent from list responses — load them lazily on first action click.
const loadedUrls = ref({
  debugUrl: props.job.debugUrl ?? null,
  textractDebugUrl: props.job.textractDebugUrl ?? null,
  croppedImageUrl: props.job.croppedImageUrl ?? null,
})
const urlsFetched = ref(
  !!(props.job.debugUrl || props.job.textractDebugUrl || props.job.croppedImageUrl)
)

const items = computed(() => (Array.isArray(props.job.items) ? props.job.items : []))
const hasDiscount = computed(() => items.value.some(it => it.discount))

const categoryLabel = computed(() => {
  if (!props.job.storeCategory) return ''
  return props.job.storeCategory.replace(/_/g, ' ')
})

// Action bar visible for all COMPLETE jobs — no longer gated on URL presence.
const canShowActions = computed(() =>
  props.showActions && props.job.status === 'COMPLETE'
)

// Cropped image may be known from a boolean flag (list) or from the URL itself (single-job).
const hasCropped = computed(() =>
  !!(loadedUrls.value.croppedImageUrl || props.job.hasCroppedImage)
)

async function fetchUrls() {
  if (urlsFetched.value || !apiFetch || !CONFIG) return
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/jobs/${props.job.jobId}`)
    if (!resp.ok) return
    const data = await resp.json()
    loadedUrls.value = {
      debugUrl: data.debugUrl ?? null,
      textractDebugUrl: data.textractDebugUrl ?? null,
      croppedImageUrl: data.croppedImageUrl ?? null,
    }
    urlsFetched.value = true
  } catch (e) {
    console.error('Failed to fetch job URLs:', e)
  }
}

async function openCroppedImage() {
  await fetchUrls()
  if (loadedUrls.value.croppedImageUrl) window.open(loadedUrls.value.croppedImageUrl, '_blank')
}

async function openDebugJson() {
  await fetchUrls()
  if (loadedUrls.value.debugUrl) window.open(loadedUrls.value.debugUrl, '_blank')
}

async function toggleDebug() {
  if (!showDebug.value) await fetchUrls()
  showDebug.value = !showDebug.value
}

const confirmingDelete = ref(false)
const deleting = ref(false)
const deleteError = ref('')

async function doDelete() {
  deleting.value = true
  deleteError.value = ''
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/receipts/${props.job.jobId}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
    emit('deleted', props.job.jobId)
  } catch (err) {
    deleteError.value = 'Failed to delete — try again.'
  } finally {
    deleting.value = false
  }
}
</script>

<template>
  <div v-if="job.status === 'DUPLICATE'" class="receipt-card receipt-card--failed">
    <p class="failed-text">Already scanned — see your history for the original receipt.</p>
  </div>

  <div v-else-if="job.status === 'FAILED'" class="receipt-card receipt-card--failed">
    <p class="failed-text">
      {{
        job.reason === 'timeout'
          ? 'Scan is taking longer than expected — try again in a moment.'
          : 'Scan failed — could not read this receipt.'
      }}
    </p>
  </div>

  <div v-else class="receipt-card">
    <div class="receipt-header">
      <span class="receipt-vendor">{{ job.vendor || 'Unknown vendor' }}</span>
      <span v-if="job.total" class="receipt-total">{{ job.total }}</span>
    </div>

    <div class="receipt-meta">
      <span v-if="job.receiptDate" class="receipt-date">{{ formatDate(job.receiptDate) }}</span>
      <span v-if="categoryLabel" class="store-category-badge">{{ categoryLabel }}</span>
    </div>

    <div v-if="job.priceCheckWarning" class="price-check-warning">
      Price check: {{ job.priceCheckMessage || 'item prices do not match total' }} — use Edit to correct
    </div>

    <table v-if="items.length" class="items-table">
      <thead>
        <tr>
          <th>Item</th>
          <th>Qty</th>
          <th>Unit price</th>
          <th v-if="hasDiscount">Discount</th>
          <th>Price</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(it, i) in items" :key="i">
          <td>
            {{ it.description }}
            <span v-if="it.package_size" class="pkg-size">{{ it.package_size }}</span>
          </td>
          <td>{{ it.quantity }}</td>
          <td>{{ it.unit_price }}</td>
          <td v-if="hasDiscount">{{ it.discount || '' }}</td>
          <td>{{ it.price }}</td>
        </tr>
      </tbody>
    </table>

    <!-- Action bar: URLs are loaded lazily from GET /jobs/{jobId} on first click -->
    <template v-if="canShowActions">
      <div class="action-bar">
        <button v-if="hasCropped" class="btn btn-secondary action-btn" @click="openCroppedImage">
          Cropped image
        </button>
        <button class="btn btn-secondary action-btn" @click="toggleDebug">
          {{ showDebug ? 'Hide OCR' : 'OCR debug' }}
        </button>
        <button class="btn btn-secondary action-btn" @click="openDebugJson">
          AI extraction JSON
        </button>
      </div>
    </template>

    <OcrDebugPanel
      v-if="canShowActions && showDebug && loadedUrls.textractDebugUrl"
      :url="loadedUrls.textractDebugUrl"
      :job-id="job.jobId"
    />

    <div v-if="showActions" class="card-footer">
      <button class="btn btn-secondary edit-btn" @click="emit('edit', job)">Edit</button>
      <button class="btn btn-danger-outline delete-btn" @click="confirmingDelete = true">Delete</button>
    </div>

    <div v-if="confirmingDelete" class="delete-confirm">
      <span class="delete-confirm-text">Delete this receipt permanently?</span>
      <span v-if="deleteError" class="delete-confirm-error">{{ deleteError }}</span>
      <div class="delete-confirm-actions">
        <button class="btn btn-secondary confirm-btn" :disabled="deleting" @click="confirmingDelete = false; deleteError = ''">Cancel</button>
        <button class="btn btn-danger confirm-btn" :disabled="deleting" @click="doDelete">
          {{ deleting ? 'Deleting…' : 'Delete' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.action-bar {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.5rem;
  flex-wrap: wrap;
  align-items: center;
}
.action-btn {
  font-size: 0.8rem;
}
.card-footer {
  margin-top: 0.5rem;
  display: flex;
  gap: 0.5rem;
}
.edit-btn,
.delete-btn {
  font-size: 0.8rem;
}
.btn-danger-outline {
  background: transparent;
  color: var(--danger);
  border: 1px solid var(--danger);
}
.btn-danger-outline:hover {
  background: var(--danger-surface);
}
.delete-confirm {
  margin-top: 0.75rem;
  padding: 0.65rem 0.75rem;
  background: var(--danger-surface);
  border-radius: 6px;
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}
.delete-confirm-text {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--danger);
  flex: 1;
}
.delete-confirm-error {
  font-size: var(--text-xs);
  color: var(--danger);
  width: 100%;
}
.delete-confirm-actions {
  display: flex;
  gap: 0.5rem;
  flex-shrink: 0;
}
.confirm-btn {
  font-size: var(--text-xs);
  padding: 0.3rem 0.75rem;
}
.btn-danger {
  background: var(--danger);
  color: #fff;
}
.btn-danger:hover:not(:disabled) {
  background: #b71c1c;
}
.btn-danger:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
</style>
