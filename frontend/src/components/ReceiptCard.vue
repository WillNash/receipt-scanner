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

const emit = defineEmits(['edit'])

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

    <button
      v-if="showActions"
      class="btn btn-secondary edit-btn"
      @click="emit('edit', job)"
    >
      Edit
    </button>
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
.edit-btn {
  margin-top: 0.5rem;
  font-size: 0.8rem;
}
</style>
