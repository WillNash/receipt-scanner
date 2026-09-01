import { ref } from 'vue'

// Module-level — shared across all component instances for the lifetime of the page
const allReceipts = ref([])
const loading = ref(false)
const loaded = ref(false)
const loadedCount = ref(0)
const error = ref(null)

export function useReceipts(apiFetch, CONFIG) {
  async function fetchAll() {
    if (loaded.value || loading.value) return
    loading.value = true
    error.value = null
    try {
      let cursor = null
      do {
        const url = cursor
          ? `${CONFIG.apiBaseUrl}/receipts?lastKey=${encodeURIComponent(cursor)}`
          : `${CONFIG.apiBaseUrl}/receipts`
        const resp = await apiFetch(url)
        if (!resp.ok) throw new Error('Failed to load receipts')
        const data = await resp.json()
        allReceipts.value.push(...(data.receipts || []))
        loadedCount.value = allReceipts.value.length
        cursor = data.lastKey ?? null
      } while (cursor)
      loaded.value = true
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  function removeReceipt(jobId) {
    allReceipts.value = allReceipts.value.filter(r => r.jobId !== jobId)
    loadedCount.value = allReceipts.value.length
  }

  function updateReceipt(jobId, patch) {
    const idx = allReceipts.value.findIndex(r => r.jobId === jobId)
    if (idx !== -1) allReceipts.value[idx] = { ...allReceipts.value[idx], ...patch }
  }

  return { allReceipts, loading, loaded, loadedCount, error, fetchAll, removeReceipt, updateReceipt }
}
