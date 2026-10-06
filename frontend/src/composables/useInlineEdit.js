import { ref } from 'vue'

export function useInlineEdit(apiFetch, CONFIG, updateReceipt, { fieldName, getInitialValue, transformValue = v => v }) {
  const editingId = ref(null)
  const editVal = ref('')
  const saving = ref(false)
  const error = ref(null)

  function startEdit(jobId, job) {
    editingId.value = jobId
    editVal.value = getInitialValue(job)
    error.value = null
  }

  function cancelEdit() {
    editingId.value = null
    error.value = null
  }

  async function saveEdit(jobId) {
    saving.value = true
    error.value = null
    try {
      const resp = await apiFetch(`${CONFIG.apiBaseUrl}/receipts/${jobId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ [fieldName]: transformValue(editVal.value) }),
      })
      if (!resp.ok) throw new Error(`Server returned ${resp.status}`)
      const updated = await resp.json()
      updateReceipt(jobId, { [fieldName]: updated[fieldName] })
      editingId.value = null
    } catch {
      error.value = 'Failed to save — try again.'
    } finally {
      saving.value = false
    }
  }

  return { editingId, editVal, saving, error, startEdit, cancelEdit, saveEdit }
}
