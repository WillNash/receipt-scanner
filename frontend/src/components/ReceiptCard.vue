<script setup>
import { ref, computed } from 'vue'
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

const showDebug = ref(false)

const items = computed(() => (Array.isArray(props.job.items) ? props.job.items : []))
const hasDiscount = computed(() => items.value.some(it => it.discount))

const categoryLabel = computed(() => {
  if (!props.job.storeCategory) return ''
  return props.job.storeCategory.replace(/_/g, ' ')
})

function toggleDebug() {
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

    <!-- Action bar: cropped image, OCR debug, AI extraction JSON, Edit -->
    <template v-if="showActions && (job.textractDebugUrl || job.debugUrl || job.croppedImageUrl)">
      <div class="action-bar">
        <a v-if="job.croppedImageUrl" :href="job.croppedImageUrl" class="btn btn-secondary action-btn">
          Cropped image
        </a>
        <button v-if="job.textractDebugUrl" class="btn btn-secondary action-btn" @click="toggleDebug">
          {{ showDebug ? 'Hide OCR' : 'OCR debug' }}
        </button>
        <a v-if="job.debugUrl" :href="job.debugUrl" class="btn btn-secondary action-btn">
          AI extraction JSON
        </a>
      </div>
    </template>

    <OcrDebugPanel
      v-if="showActions && showDebug && job.textractDebugUrl"
      :url="job.textractDebugUrl"
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
