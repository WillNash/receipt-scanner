<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { formatDate } from '../utils.js'

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')
const route = useRoute()
const router = useRouter()

const job = ref(null)
const loading = ref(true)
const error = ref(null)

onMounted(async () => {
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/jobs/${route.params.jobId}`)
    if (!resp.ok) throw new Error('Failed to load receipt')
    job.value = await resp.json()
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
})

const items = computed(() => Array.isArray(job.value?.items) ? job.value.items : [])
const hasDiscount = computed(() => items.value.some(it => it.discount))
const hasWeightQty = computed(() => items.value.some(it => it.package_size))
const categoryLabel = computed(() =>
  job.value?.storeCategory ? job.value.storeCategory.replace(/_/g, ' ') : ''
)
</script>

<template>
  <div class="detail-view">
    <button class="btn btn-secondary back-btn" @click="router.push('/list')">← Back to list</button>

    <div v-if="loading" class="state-text">Loading receipt…</div>
    <div v-else-if="error" class="state-text state-text--error">{{ error }}</div>

    <template v-else-if="job">
      <div class="detail-header">
        <h2 class="detail-vendor">{{ job.vendor || 'Unknown vendor' }}</h2>
        <div class="detail-meta">
          <span v-if="categoryLabel" class="store-category-badge">{{ categoryLabel }}</span>
          <span v-if="job.receiptDate" class="meta-item">{{ formatDate(job.receiptDate) }}</span>
          <span v-if="job.total" class="meta-item detail-total">{{ job.total }}</span>
        </div>
      </div>

      <div v-if="items.length === 0" class="state-text">No line items found.</div>

      <table v-else class="items-table">
        <thead>
          <tr>
            <th>Item</th>
            <th>Category</th>
            <th>Qty</th>
            <th v-if="hasWeightQty">Weight qty</th>
            <th>Unit price</th>
            <th v-if="hasDiscount">Discount</th>
            <th>Price</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(it, i) in items" :key="i">
            <td>{{ it.description || '—' }}</td>
            <td>{{ it.item_category || '—' }}</td>
            <td>{{ it.quantity || '—' }}</td>
            <td v-if="hasWeightQty">{{ it.package_size || '—' }}</td>
            <td>{{ it.unit_price || '—' }}</td>
            <td v-if="hasDiscount">{{ it.discount || '' }}</td>
            <td>{{ it.price || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<style scoped>
.detail-view {
  padding: 0.5rem 0;
}

.back-btn {
  margin-bottom: 1.5rem;
}

.detail-header {
  margin-bottom: 1.5rem;
}

.detail-vendor {
  font-size: var(--text-xl);
  font-weight: 700;
  margin-bottom: 0.5rem;
}

.detail-meta {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.meta-item {
  font-size: var(--text-sm);
  color: var(--muted);
}

.detail-total {
  font-weight: 700;
  font-size: var(--text-base);
  color: var(--text);
}

.items-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
}

.items-table th,
.items-table td {
  padding: 0.65rem 0.9rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
  font-size: var(--text-sm);
}

.items-table th {
  font-weight: 600;
  background: #f8f8f8;
  color: var(--muted);
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.03em;
}

.items-table tbody tr:last-child td {
  border-bottom: none;
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
