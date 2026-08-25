<script setup>
import { ref, computed, inject, onMounted, onUnmounted } from 'vue'

const props = defineProps({
  job: {
    type: Object,
    required: true,
  },
})

const emit = defineEmits(['close', 'saved'])

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')

const vendor = ref(props.job.vendor || '')
const receiptDate = ref(props.job.receiptDate || '')
const editItems = ref(
  (Array.isArray(props.job.items) ? props.job.items : []).map(it => ({ ...it }))
)
const saving = ref(false)

const receiptTotal = parseFloat(props.job.total) || 0

const priceSum = computed(() => {
  let sum = 0
  for (const it of editItems.value) {
    const v = parseFloat(String(it.price || '').replace(/[,$]/g, '').trim())
    if (!isNaN(v)) sum += v
  }
  return Math.round(sum * 100) / 100
})

const priceDiff = computed(() => Math.round((priceSum.value - receiptTotal) * 100) / 100)
const priceOk = computed(() => Math.abs(priceDiff.value) < 0.01)

const priceSumText = computed(() => {
  const base = `Items sum: $${priceSum.value.toFixed(2)} / Receipt total: $${receiptTotal.toFixed(2)}`
  if (priceOk.value) return base + '  ✓'
  return base + `  — ${priceDiff.value > 0 ? 'over' : 'under'} by $${Math.abs(priceDiff.value).toFixed(2)}`
})

function addItem() {
  editItems.value.push({
    description: '',
    quantity: '',
    package_size: '',
    unit_price: '',
    price: '',
    discount: '',
  })
}

function deleteItem(i) {
  editItems.value.splice(i, 1)
}

function onOverlayClick(e) {
  if (e.target === e.currentTarget) emit('close')
}

function onEscape(e) {
  if (e.key === 'Escape') emit('close')
}

onMounted(() => {
  document.addEventListener('keydown', onEscape)
})

onUnmounted(() => {
  document.removeEventListener('keydown', onEscape)
})

async function save() {
  saving.value = true
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/receipts/${props.job.jobId}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        vendor: vendor.value.trim(),
        receiptDate: receiptDate.value.trim(),
        items: editItems.value,
      }),
    })
    if (!resp.ok) throw new Error(await resp.text())
    emit('saved')
    emit('close')
  } catch (err) {
    saving.value = false
    alert('Failed to save: ' + err.message)
  }
}
</script>

<template>
  <div class="modal-overlay" @click="onOverlayClick">
    <div class="modal-box" role="dialog" aria-modal="true" aria-label="Edit Receipt">
      <div class="modal-header">
        <h3>Edit Receipt</h3>
        <button class="close-btn" @click="emit('close')">&#x2715;</button>
      </div>

      <div class="field-group">
        <label class="field-label">Store / Vendor</label>
        <input v-model="vendor" type="text" class="field-input" />
      </div>

      <div class="field-group">
        <label class="field-label">Receipt date (YYYY-MM-DD)</label>
        <input v-model="receiptDate" type="text" class="field-input" />
      </div>

      <div class="field-group">
        <div class="items-header">
          <p class="items-label">Line items</p>
          <button class="btn btn-secondary add-item-btn" @click="addItem">+ Add item</button>
        </div>

        <div class="items-container">
          <div v-for="(it, i) in editItems" :key="i" class="item-row">
            <!-- Row 1: index + description + delete -->
            <div class="item-top-row">
              <span class="item-index">{{ i + 1 }}.</span>
              <input
                v-model="it.description"
                type="text"
                placeholder="Description"
                class="item-input item-input--desc"
              />
              <button class="item-delete-btn" title="Delete item" @click="deleteItem(i)">×</button>
            </div>

            <!-- Row 2: numeric fields -->
            <div class="item-num-row">
              <input v-model="it.quantity"     type="text" placeholder="Qty"        class="item-input item-input--num" style="width:15%" />
              <input v-model="it.package_size" type="text" placeholder="Pkg size"   class="item-input item-input--num" style="width:15%" />
              <input v-model="it.unit_price"   type="text" placeholder="Unit price" class="item-input item-input--num" style="width:22%" />
              <input v-model="it.price"        type="text" placeholder="Price"      class="item-input item-input--num" style="width:22%" />
              <input v-model="it.discount"     type="text" placeholder="Discount"   class="item-input item-input--num" style="width:22%" />
            </div>
          </div>
        </div>

        <div class="price-sum-bar" :class="priceOk ? 'price-sum--ok' : 'price-sum--warn'">
          {{ priceSumText }}
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn btn-secondary" @click="emit('close')">Cancel</button>
        <button class="btn btn-primary" :disabled="saving" @click="save">
          {{ saving ? 'Saving…' : 'Save' }}
        </button>
      </div>
    </div>
  </div>
</template>

<style scoped>
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
}

.modal-box {
  background: #fff;
  border-radius: 8px;
  padding: 1.5rem;
  width: min(560px, 92vw);
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.2);
}

.modal-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 1rem;
}

.modal-header h3 {
  margin: 0;
}

.close-btn {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 1.2rem;
}

.field-group {
  margin-bottom: 0.75rem;
}

.field-label {
  display: block;
  font-size: 0.8rem;
  margin-bottom: 2px;
}

.field-input {
  width: 100%;
  padding: 0.4rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
}

.items-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 0.4rem;
}

.items-label {
  font-weight: 500;
  margin: 0;
}

.add-item-btn {
  font-size: 0.75rem;
  padding: 0.25rem 0.7rem;
}

.items-container {
  display: flex;
  flex-direction: column;
  gap: 0;
}

.item-row {
  margin-bottom: 0.5rem;
  border: 1px solid #eee;
  border-radius: 4px;
  padding: 0.45rem 0.5rem;
}

.item-top-row {
  display: flex;
  gap: 0.3rem;
  align-items: center;
  margin-bottom: 3px;
}

.item-index {
  font-size: 0.7rem;
  color: #aaa;
  min-width: 1.4rem;
  flex-shrink: 0;
}

.item-input {
  padding: 0.32rem 0.4rem;
  border: 1px solid #ccc;
  border-radius: 4px;
  box-sizing: border-box;
  font-size: 0.82rem;
}

.item-input--desc {
  width: 100%;
  flex: 1;
}

.item-input--num {
  flex-shrink: 0;
}

.item-delete-btn {
  flex-shrink: 0;
  padding: 0.2rem 0.55rem;
  background: #fee2e2;
  border: none;
  border-radius: 4px;
  color: #dc2626;
  cursor: pointer;
  font-size: 1rem;
  line-height: 1;
}

.item-num-row {
  display: flex;
  gap: 0.3rem;
}

.price-sum-bar {
  margin-top: 0.5rem;
  padding: 0.4rem 0.6rem;
  border-radius: 4px;
  font-size: 0.8rem;
}

.price-sum--ok {
  background: #e8f5e9;
  color: #2e7d32;
}

.price-sum--warn {
  background: #fff3e0;
  color: #e65100;
}

.modal-footer {
  display: flex;
  gap: 0.5rem;
  justify-content: flex-end;
  margin-top: 0.75rem;
}
</style>
