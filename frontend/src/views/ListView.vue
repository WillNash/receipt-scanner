<script setup>
import { ref, computed, inject, onMounted, watch } from 'vue'
import { useRouter } from 'vue-router'
import { formatDate, parseCurrency } from '../utils.js'
import { useReceipts } from '../composables/useReceipts.js'
import { useInlineEdit } from '../composables/useInlineEdit.js'

const ISO_DATE_RE = /^\d{4}-\d{2}-\d{2}$/
function isIsoDate(date) {
  return !!date && ISO_DATE_RE.test(date)
}

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')
const router = useRouter()

const { allReceipts, loading, error, fetchAll, removeReceipt, updateReceipt } = useReceipts(apiFetch, CONFIG)

onMounted(fetchAll)

const storeNames = ref([])
onMounted(() => {
  apiFetch(`${CONFIG.apiBaseUrl}/stores`)
    .then(r => r.ok ? r.json() : Promise.reject(new Error(`GET /stores ${r.status}`)))
    .then(data => { if (Array.isArray(data.stores)) storeNames.value = data.stores })
    .catch(err => console.warn('Store list unavailable:', err))
})

const receipts = computed(() => allReceipts.value.filter(r => r.status === 'COMPLETE'))

// --- Sort & filter ---
const sortField = ref('receiptDate')
const sortDir = ref('desc')
const filterStore = ref('')

const storeOptions = computed(() => {
  const vendors = receipts.value.map(r => r.vendor).filter(Boolean)
  return [...new Set(vendors)].sort()
})

const filtered = computed(() => {
  if (!filterStore.value) return receipts.value
  return receipts.value.filter(r => r.vendor === filterStore.value)
})

const SORT_EXTRACTORS = {
  vendor:      r => (r.vendor || '').toLowerCase(),
  receiptDate: r => r.receiptDate || '',
  total:       r => parseCurrency(r.total),
}

const sorted = computed(() => {
  const extract = SORT_EXTRACTORS[sortField.value] ?? (() => '')
  const dir = sortDir.value === 'asc' ? 1 : -1
  return [...filtered.value].sort((a, b) => {
    const av = extract(a), bv = extract(b)
    return av < bv ? -dir : av > bv ? dir : 0
  })
})

// --- Pagination ---
const PAGE_SIZE = 20
const currentPage = ref(1)
const totalPages = computed(() => Math.max(1, Math.ceil(sorted.value.length / PAGE_SIZE)))
const paginated = computed(() => {
  const start = (currentPage.value - 1) * PAGE_SIZE
  return sorted.value.slice(start, start + PAGE_SIZE)
})

watch([sortField, sortDir, filterStore], () => { currentPage.value = 1 })
watch(sorted, () => {
  if (currentPage.value > totalPages.value) currentPage.value = totalPages.value
})

// --- Sort helpers ---
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

// --- Delete ---
const confirmingId = ref(null)
const deletingId = ref(null)
const deleteError = ref(null)

function startDelete(jobId) {
  deleteError.value = null
  confirmingId.value = jobId
}

function cancelDelete() {
  confirmingId.value = null
  deleteError.value = null
}

async function confirmDelete(jobId) {
  deletingId.value = jobId
  deleteError.value = null
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/receipts/${jobId}`, { method: 'DELETE' })
    if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
    removeReceipt(jobId)
    confirmingId.value = null
  } catch {
    deleteError.value = 'Failed to delete — try again.'
  } finally {
    deletingId.value = null
  }
}

// --- Inline edits ---
const {
  editingId: dateEditingId, editVal: dateEditVal, saving: dateSaving, error: dateEditError,
  startEdit: startDateEdit, cancelEdit: cancelDateEdit, saveEdit: saveDateEdit,
} = useInlineEdit(apiFetch, CONFIG, updateReceipt, {
  fieldName: 'receiptDate',
  getInitialValue: job => isIsoDate(job.receiptDate) ? job.receiptDate : '',
})

const {
  editingId: vendorEditingId, editVal: vendorEditVal, saving: vendorSaving, error: vendorEditError,
  startEdit: startVendorEdit, cancelEdit: cancelVendorEdit, saveEdit: saveVendorEdit,
} = useInlineEdit(apiFetch, CONFIG, updateReceipt, {
  fieldName: 'vendor',
  getInitialValue: job => job.vendor || '',
  transformValue: v => v.trim(),
})
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
        <span class="receipt-count">{{ sorted.length }} receipt{{ sorted.length !== 1 ? 's' : '' }}</span>
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
          <template v-for="job in paginated" :key="job.jobId">
            <!-- Confirmation row -->
            <tr v-if="confirmingId === job.jobId" class="confirm-row">
              <td colspan="5">
                <div class="confirm-inner">
                  <span class="confirm-text">Delete this receipt permanently?</span>
                  <span v-if="deleteError" class="confirm-error">{{ deleteError }}</span>
                  <div class="confirm-actions">
                    <button
                      class="btn btn-secondary confirm-btn"
                      :disabled="deletingId === job.jobId"
                      @click.stop="cancelDelete()"
                    >Cancel</button>
                    <button
                      class="btn btn-danger confirm-btn"
                      :disabled="deletingId === job.jobId"
                      @click.stop="confirmDelete(job.jobId)"
                    >{{ deletingId === job.jobId ? 'Deleting…' : 'Delete' }}</button>
                  </div>
                </div>
              </td>
            </tr>

            <!-- Normal row -->
            <tr v-else class="receipt-row" @click="router.push(`/receipt/${job.jobId}`)">
              <td class="vendor-cell">
                <template v-if="vendorEditingId === job.jobId">
                  <div class="field-edit-row" @click.stop>
                    <input
                      type="text"
                      list="vendor-store-options"
                      v-model="vendorEditVal"
                      class="field-edit-input"
                      autocomplete="off"
                      placeholder="Type to search…"
                    />
                    <datalist id="vendor-store-options">
                      <option v-for="name in storeNames" :key="name" :value="name" />
                    </datalist>
                    <button
                      class="btn btn-primary save-field-btn"
                      :disabled="vendorSaving"
                      @click.stop="saveVendorEdit(job.jobId)"
                    >{{ vendorSaving ? '…' : 'Save' }}</button>
                    <button
                      class="btn btn-secondary save-field-btn"
                      :disabled="vendorSaving"
                      @click.stop="cancelVendorEdit()"
                    >Cancel</button>
                    <span v-if="vendorEditError" class="field-edit-error">{{ vendorEditError }}</span>
                  </div>
                </template>
                <template v-else>
                  <span>{{ job.vendor || '—' }}</span>
                  <button class="edit-icon-btn" title="Edit store" @click.stop="startVendorEdit(job.jobId, job)">&#x270F;</button>
                </template>
              </td>
              <td>{{ job.storeCategory ? job.storeCategory.replace(/_/g, ' ') : '—' }}</td>
              <td class="date-cell">
                <template v-if="dateEditingId === job.jobId">
                  <div class="field-edit-row" @click.stop>
                    <input type="date" v-model="dateEditVal" class="field-edit-input" />
                    <button
                      class="btn btn-primary save-field-btn"
                      :disabled="dateSaving || !dateEditVal"
                      @click.stop="saveDateEdit(job.jobId)"
                    >{{ dateSaving ? '…' : 'Save' }}</button>
                    <button
                      class="btn btn-secondary save-field-btn"
                      :disabled="dateSaving"
                      @click.stop="cancelDateEdit()"
                    >Cancel</button>
                    <span v-if="dateEditError" class="field-edit-error">{{ dateEditError }}</span>
                  </div>
                </template>
                <template v-else>
                  <span v-if="!isIsoDate(job.receiptDate)" class="badge-icon date-flag" title="Date not in standard format">!</span>
                  <span class="date-text">{{ job.receiptDate ? formatDate(job.receiptDate) : '—' }}</span>
                  <button class="edit-icon-btn" title="Edit date" @click.stop="startDateEdit(job.jobId, job)">&#x270F;</button>
                </template>
              </td>
              <td class="total-cell">
                <span v-if="job.priceCheckWarning" class="badge-icon price-warn" :title="job.priceCheckMessage || 'Item prices do not match total'">!</span>
                {{ job.total || '—' }}
              </td>
              <td class="col-action">
                <button class="delete-btn" title="Delete receipt" @click.stop="startDelete(job.jobId)">&#x1F5D1;</button>
              </td>
            </tr>
          </template>
        </tbody>
      </table>

      <!-- Pagination -->
      <div v-if="totalPages > 1" class="pagination">
        <button class="btn btn-secondary page-btn" :disabled="currentPage === 1" @click="currentPage--">&#8592; Prev</button>
        <span class="page-info">Page {{ currentPage }} of {{ totalPages }}</span>
        <button class="btn btn-secondary page-btn" :disabled="currentPage === totalPages" @click="currentPage++">Next &#8594;</button>
      </div>
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

.receipt-count {
  font-size: var(--text-xs);
  color: var(--muted);
  margin-left: auto;
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

.receipt-row:hover .delete-btn,
.receipt-row:hover .edit-icon-btn {
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

/* Shared badge (price warning, date flag) */
.badge-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 1.1rem;
  height: 1.1rem;
  border-radius: 50%;
  color: #fff;
  font-size: 0.65rem;
  font-weight: 700;
  margin-right: 0.3rem;
  vertical-align: middle;
  line-height: 1;
}

.price-warn { background: var(--danger); cursor: default; }
.date-flag  { background: #f59e0b; }

/* Shared inline-edit pencil button */
.edit-icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 0.85rem;
  padding: 0.15rem 0.25rem;
  opacity: 0;
  transition: opacity 0.1s, color 0.1s;
  color: var(--muted);
  line-height: 1;
  vertical-align: middle;
  margin-left: 0.2rem;
}

.edit-icon-btn:hover { color: var(--accent); }

/* Shared inline-edit row layout */
.field-edit-row {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.field-edit-input {
  padding: 0.2rem 0.4rem;
  border: 1px solid var(--border);
  border-radius: 4px;
  font-size: var(--text-sm);
  background: var(--surface);
  min-width: 8rem;
}

.save-field-btn {
  font-size: var(--text-xs);
  padding: 0.25rem 0.6rem;
  white-space: nowrap;
}

.field-edit-error {
  font-size: var(--text-xs);
  color: var(--danger);
}

.vendor-cell { white-space: nowrap; }
.date-cell   { white-space: nowrap; }
.total-cell  { white-space: nowrap; }

/* Confirm row */
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

.btn-danger:hover:not(:disabled) { background: #b71c1c; }
.btn-danger:disabled { opacity: 0.6; cursor: not-allowed; }

/* Pagination */
.pagination {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 1rem;
  margin-top: 1rem;
}

.page-btn {
  font-size: var(--text-sm);
  padding: 0.35rem 0.85rem;
}

.page-info {
  font-size: var(--text-sm);
  color: var(--muted);
  min-width: 8rem;
  text-align: center;
}

.state-text {
  text-align: center;
  padding: 3rem;
  color: var(--muted);
}

.state-text--error { color: var(--danger); }
</style>
