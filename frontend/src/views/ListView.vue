<script setup>
import { ref, computed, inject, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { formatDate } from '../utils.js'

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')
const router = useRouter()

const receipts = ref([])
const loading = ref(true)
const error = ref(null)

const sortField = ref('receiptDate')
const sortDir = ref('desc')
const filterStore = ref('')

onMounted(async () => {
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/receipts`)
    if (!resp.ok) throw new Error('Failed to load receipts')
    const data = await resp.json()
    receipts.value = (data.receipts || []).filter(r => r.status === 'COMPLETE')
  } catch (err) {
    error.value = err.message
  } finally {
    loading.value = false
  }
})

const storeOptions = computed(() => {
  const vendors = receipts.value.map(r => r.vendor).filter(Boolean)
  return [...new Set(vendors)].sort()
})

const filtered = computed(() => {
  if (!filterStore.value) return receipts.value
  return receipts.value.filter(r => r.vendor === filterStore.value)
})

const sorted = computed(() => {
  return [...filtered.value].sort((a, b) => {
    let av, bv
    if (sortField.value === 'vendor') {
      av = (a.vendor || '').toLowerCase()
      bv = (b.vendor || '').toLowerCase()
    } else if (sortField.value === 'receiptDate') {
      av = a.receiptDate || ''
      bv = b.receiptDate || ''
    } else if (sortField.value === 'total') {
      av = parseFloat((a.total || '0').replace(/[^0-9.-]/g, '')) || 0
      bv = parseFloat((b.total || '0').replace(/[^0-9.-]/g, '')) || 0
    }
    if (av < bv) return sortDir.value === 'asc' ? -1 : 1
    if (av > bv) return sortDir.value === 'asc' ? 1 : -1
    return 0
  })
})

function setSort(field) {
  if (sortField.value === field) {
    sortDir.value = sortDir.value === 'asc' ? 'desc' : 'asc'
  } else {
    sortField.value = field
    sortDir.value = 'asc'
  }
}

function sortIndicator(field) {
  if (sortField.value !== field) return ''
  return sortDir.value === 'asc' ? ' ▲' : ' ▼'
}
</script>

<template>
  <div class="list-view">
    <div v-if="loading" class="state-text">Loading receipts…</div>
    <div v-else-if="error" class="state-text state-text--error">{{ error }}</div>

    <template v-else>
      <div class="list-controls">
        <label class="filter-label">
          Store
          <select v-model="filterStore" class="filter-select">
            <option value="">All stores</option>
            <option v-for="store in storeOptions" :key="store" :value="store">{{ store }}</option>
          </select>
        </label>
      </div>

      <div v-if="sorted.length === 0" class="state-text">No receipts found.</div>

      <table v-else class="receipts-table">
        <thead>
          <tr>
            <th class="sortable" @click="setSort('vendor')">Store{{ sortIndicator('vendor') }}</th>
            <th>Type</th>
            <th class="sortable" @click="setSort('receiptDate')">Date{{ sortIndicator('receiptDate') }}</th>
            <th class="sortable" @click="setSort('total')">Total{{ sortIndicator('total') }}</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="job in sorted"
            :key="job.jobId"
            class="receipt-row"
            @click="router.push(`/receipt/${job.jobId}`)"
          >
            <td>{{ job.vendor || '—' }}</td>
            <td>{{ job.storeCategory ? job.storeCategory.replace(/_/g, ' ') : '—' }}</td>
            <td>{{ job.receiptDate ? formatDate(job.receiptDate) : '—' }}</td>
            <td>{{ job.total || '—' }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </div>
</template>

<style scoped>
.list-view {
  padding: 0.5rem 0;
}

.list-controls {
  display: flex;
  gap: 1rem;
  margin-bottom: 1rem;
  align-items: center;
}

.filter-label {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-sm);
  font-weight: 600;
}

.filter-select {
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: var(--text-sm);
  background: var(--surface);
  cursor: pointer;
}

.receipts-table {
  width: 100%;
  border-collapse: collapse;
  background: var(--surface);
  border-radius: var(--radius);
  overflow: hidden;
  box-shadow: var(--shadow);
}

.receipts-table th,
.receipts-table td {
  padding: 0.65rem 0.9rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
  font-size: var(--text-sm);
}

.receipts-table th {
  font-weight: 600;
  background: #f8f8f8;
  color: var(--muted);
  text-transform: uppercase;
  font-size: 0.75rem;
  letter-spacing: 0.03em;
}

.receipts-table tbody tr:last-child td {
  border-bottom: none;
}

.sortable {
  cursor: pointer;
  user-select: none;
}

.sortable:hover {
  background: #efefef;
}

.receipt-row {
  cursor: pointer;
  transition: background 0.1s;
}

.receipt-row:hover {
  background: #f5f8ff;
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
