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

const confirmingId = ref(null) // jobId currently showing delete confirmation
const deletingId = ref(null)   // jobId mid-delete API call
const deleteError = ref(null)

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

function startDelete(e, jobId) {
  e.stopPropagation()
  deleteError.value = null
  confirmingId.value = jobId
}

function cancelDelete(e) {
  e.stopPropagation()
  confirmingId.value = null
  deleteError.value = null
}

async function confirmDelete(e, jobId) {
  e.stopPropagation()
  deletingId.value = jobId
  deleteError.value = null
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/receipts/${jobId}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
    receipts.value = receipts.value.filter(r => r.jobId !== jobId)
    confirmingId.value = null
  } catch (err) {
    deleteError.value = { jobId, message: 'Failed to delete — try again.' }
  } finally {
    deletingId.value = null
  }
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
            <th class="col-action"></th>
          </tr>
        </thead>
        <tbody>
          <template v-for="job in sorted" :key="job.jobId">
            <!-- Confirmation row -->
            <tr v-if="confirmingId === job.jobId" class="confirm-row">
              <td colspan="5">
                <div class="confirm-inner">
                  <span class="confirm-text">Delete this receipt permanently?</span>
                  <span v-if="deleteError?.jobId === job.jobId" class="confirm-error">
                    {{ deleteError.message }}
                  </span>
                  <div class="confirm-actions">
                    <button
                      class="btn btn-secondary confirm-btn"
                      :disabled="deletingId === job.jobId"
                      @click="cancelDelete($event)"
                    >Cancel</button>
                    <button
                      class="btn btn-danger confirm-btn"
                      :disabled="deletingId === job.jobId"
                      @click="confirmDelete($event, job.jobId)"
                    >{{ deletingId === job.jobId ? 'Deleting…' : 'Delete' }}</button>
                  </div>
                </div>
              </td>
            </tr>

            <!-- Normal row -->
            <tr
              v-else
              class="receipt-row"
              @click="router.push(`/receipt/${job.jobId}`)"
            >
              <td>{{ job.vendor || '—' }}</td>
              <td>{{ job.storeCategory ? job.storeCategory.replace(/_/g, ' ') : '—' }}</td>
              <td>{{ job.receiptDate ? formatDate(job.receiptDate) : '—' }}</td>
              <td>{{ job.total || '—' }}</td>
              <td class="col-action">
                <button
                  class="delete-btn"
                  title="Delete receipt"
                  @click="startDelete($event, job.jobId)"
                >&#x1F5D1;</button>
              </td>
            </tr>
          </template>
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

.col-action {
  width: 2.5rem;
  padding-left: 0.25rem !important;
  padding-right: 0.5rem !important;
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

.receipt-row:hover .delete-btn {
  opacity: 1;
}

.delete-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1rem;
  padding: 0.2rem;
  opacity: 0;
  transition: opacity 0.1s, color 0.1s;
  color: var(--muted);
  line-height: 1;
}

.delete-btn:hover {
  color: var(--danger);
}

.confirm-row td {
  background: var(--danger-surface);
  border-bottom: 1px solid #f5c6cb;
}

.confirm-inner {
  display: flex;
  align-items: center;
  gap: 0.75rem;
  flex-wrap: wrap;
}

.confirm-text {
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--danger);
  flex: 1;
}

.confirm-error {
  font-size: var(--text-xs);
  color: var(--danger);
}

.confirm-actions {
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

.state-text {
  text-align: center;
  padding: 3rem;
  color: var(--muted);
}

.state-text--error {
  color: var(--danger);
}
</style>
