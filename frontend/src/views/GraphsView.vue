<script setup>
import { ref, computed, inject, onMounted, onUnmounted, watch, nextTick } from 'vue'
import { Chart, registerables } from 'chart.js'
import RangeSlider from '../components/RangeSlider.vue'

Chart.register(...registerables)

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')

// --- Data loading (all pages) ---
const allReceipts = ref([])
const loading = ref(true)
const loadingMsg = ref('Loading receipts…')
const error = ref(null)

onMounted(async () => {
  try {
    let cursor = null
    let page = 1
    do {
      if (page > 1) loadingMsg.value = `Loading receipts (page ${page})…`
      const url = cursor
        ? `${CONFIG.apiBaseUrl}/receipts?lastKey=${encodeURIComponent(cursor)}`
        : `${CONFIG.apiBaseUrl}/receipts`
      const resp = await apiFetch(url)
      if (!resp.ok) throw new Error('Failed to load receipts')
      const data = await resp.json()
      allReceipts.value.push(...(data.receipts || []))
      cursor = data.lastKey ?? null
      page++
    } while (cursor)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})

// --- Date range slider ---
const DAY_MS = 86_400_000

const sliderMin = computed(() => {
  const dates = allReceipts.value
    .filter(r => r.receiptDate)
    .map(r => parseDateLocal(r.receiptDate))
    .filter(ts => !isNaN(ts))
  return dates.length ? Math.min(...dates) : Date.now() - DAY_MS
})

const sliderMax = computed(() => {
  const d = new Date()
  d.setHours(23, 59, 59, 999)
  return d.getTime()
})

const dateRange = ref([0, 1])

// Initialise range once loading finishes
watch(loading, isLoading => {
  if (!isLoading) dateRange.value = [sliderMin.value, sliderMax.value]
})

function fmtTs(ts) {
  return new Date(ts).toLocaleDateString()
}

// --- Filters ---
const groupBy = ref('day')
const filterStore = ref('')
const filterCategory = ref('')

const storeOptions = computed(() => {
  const vendors = allReceipts.value.map(r => r.vendor).filter(Boolean)
  return [...new Set(vendors)].sort()
})

const categoryOptions = computed(() => {
  const cats = allReceipts.value
    .flatMap(r => (r.items || []).map(it => it.item_category).filter(Boolean))
  return [...new Set(cats)].sort()
})

// --- Chart data ---
function parseAmount(str) {
  return parseFloat((str || '0').replace(/[^0-9.-]/g, '')) || 0
}

// Parse a date string to a local-midnight timestamp.
// YYYY-MM-DD strings are spec-defined as UTC midnight by Date.parse(),
// so we split manually to get local midnight instead.
function parseDateLocal(dateStr) {
  if (!dateStr) return NaN
  const m = dateStr.match(/^(\d{4})-(\d{2})-(\d{2})/)
  if (m) return new Date(+m[1], +m[2] - 1, +m[3]).getTime()
  return new Date(dateStr).getTime()
}

// Format a Date object to YYYY-MM-DD using local time fields.
function toDateKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

function mondayOf(dateStr) {
  const d = new Date(parseDateLocal(dateStr))
  d.setDate(d.getDate() - (d.getDay() + 6) % 7)
  return toDateKey(d)
}

const chartData = computed(() => {
  const [startMs, endMs] = dateRange.value

  // Accumulate spend into date buckets
  const buckets = {}
  for (const r of allReceipts.value) {
    if (!r.receiptDate) continue
    const ts = parseDateLocal(r.receiptDate)
    if (isNaN(ts) || ts < startMs || ts > endMs) continue
    if (filterStore.value && r.vendor !== filterStore.value) continue

    let spend
    if (filterCategory.value) {
      const matching = (r.items || []).filter(it => it.item_category === filterCategory.value)
      if (!matching.length) continue
      spend = matching.reduce((sum, it) => sum + parseAmount(it.price), 0)
    } else {
      spend = parseAmount(r.total)
    }

    const key = groupBy.value === 'week' ? mondayOf(r.receiptDate) : r.receiptDate
    buckets[key] = (buckets[key] || 0) + spend
  }

  // Generate every time slot in the range so the axis is linear —
  // slots with no spending get a 0 value instead of being omitted.
  const labels = []
  const values = []

  if (groupBy.value === 'day') {
    const cur = new Date(startMs)
    cur.setHours(0, 0, 0, 0)
    const end = new Date(endMs)
    end.setHours(0, 0, 0, 0)
    while (cur <= end) {
      const key = toDateKey(cur)
      labels.push(key)
      values.push(Math.round((buckets[key] || 0) * 100) / 100)
      cur.setDate(cur.getDate() + 1)
    }
  } else {
    // Start on the Monday of the week containing startMs
    const cur = new Date(startMs)
    cur.setHours(0, 0, 0, 0)
    cur.setDate(cur.getDate() - (cur.getDay() + 6) % 7)
    const end = new Date(endMs)
    while (cur <= end) {
      const key = toDateKey(cur)
      labels.push(key)
      values.push(Math.round((buckets[key] || 0) * 100) / 100)
      cur.setDate(cur.getDate() + 7)
    }
  }

  return { labels, values }
})

// --- Chart rendering ---
const canvasRef = ref(null)
let chart = null

function buildChart() {
  if (!canvasRef.value) return
  if (chart) { chart.destroy(); chart = null }

  const { labels, values } = chartData.value
  if (!labels.length) return

  chart = new Chart(canvasRef.value, {
    type: 'bar',
    data: {
      labels: labels.map(l =>
        groupBy.value === 'week'
          ? `w/c ${new Date(l).toLocaleDateString()}`
          : new Date(l).toLocaleDateString()
      ),
      datasets: [{
        data: values,
        backgroundColor: 'rgba(21, 88, 176, 0.72)',
        borderColor: 'rgba(21, 88, 176, 1)',
        borderWidth: 1,
        borderRadius: 4,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: {
        legend: { display: false },
        title: {
          display: true,
          text: groupBy.value === 'week' ? 'Spend by Week' : 'Spend by Day',
          font: { size: 15, weight: '600' },
          padding: { bottom: 12 },
        },
        tooltip: {
          callbacks: { label: ctx => `$${ctx.parsed.y.toFixed(2)}` },
        },
      },
      scales: {
        y: {
          beginAtZero: true,
          ticks: { callback: v => `$${v}` },
          title: {
            display: true,
            text: 'Price ($)',
            font: { size: 12, weight: '600' },
          },
        },
        x: {
          title: {
            display: true,
            text: groupBy.value === 'week' ? 'Week' : 'Date',
            font: { size: 12, weight: '600' },
          },
          ticks: {
            maxRotation: 45,
            minRotation: 0,
            maxTicksLimit: groupBy.value === 'week' ? 26 : 16,
            autoSkip: true,
          },
        },
      },
    },
  })
}

watch([chartData, canvasRef], () => { nextTick(buildChart) }, { flush: 'post' })

onUnmounted(() => { if (chart) chart.destroy() })
</script>

<template>
  <div class="graphs-view">
    <div v-if="loading" class="state-text">{{ loadingMsg }}</div>
    <div v-else-if="error" class="state-text state-text--error">{{ error }}</div>

    <template v-else>
      <!-- Controls -->
      <div class="controls">
        <div class="control-group">
          <span class="control-label">Group by</span>
          <div class="toggle-group">
            <button class="toggle-btn" :class="{ active: groupBy === 'day' }" @click="groupBy = 'day'">Day</button>
            <button class="toggle-btn" :class="{ active: groupBy === 'week' }" @click="groupBy = 'week'">Week</button>
          </div>
        </div>

        <div class="control-group">
          <label class="control-label" for="g-store">Store</label>
          <select id="g-store" v-model="filterStore" class="filter-select">
            <option value="">All stores</option>
            <option v-for="s in storeOptions" :key="s" :value="s">{{ s }}</option>
          </select>
        </div>

        <div class="control-group">
          <label class="control-label" for="g-cat">Category</label>
          <select id="g-cat" v-model="filterCategory" class="filter-select">
            <option value="">All categories</option>
            <option v-for="c in categoryOptions" :key="c" :value="c">{{ c }}</option>
          </select>
        </div>
      </div>

      <!-- Date range slider -->
      <div class="date-range-box">
        <div class="date-range-labels">
          <span>{{ fmtTs(dateRange[0]) }}</span>
          <span class="range-title">Date range</span>
          <span>{{ fmtTs(dateRange[1]) }}</span>
        </div>
        <RangeSlider
          v-model="dateRange"
          :min="sliderMin"
          :max="sliderMax"
          :step="DAY_MS"
        />
      </div>

      <!-- Chart -->
      <div v-if="chartData.labels.length === 0" class="state-text">
        No data for the selected filters.
      </div>
      <div v-else class="chart-wrap">
        <canvas ref="canvasRef" />
      </div>
    </template>
  </div>
</template>

<style scoped>
.graphs-view {
  padding: 0.5rem 0;
}

.controls {
  display: flex;
  flex-wrap: wrap;
  gap: 0.75rem 1.5rem;
  margin-bottom: 1.25rem;
  align-items: flex-end;
}

.control-group {
  display: flex;
  flex-direction: column;
  gap: 0.3rem;
}

.control-label {
  font-size: 0.72rem;
  font-weight: 600;
  color: var(--muted);
  text-transform: uppercase;
  letter-spacing: 0.04em;
}

.toggle-group {
  display: flex;
  border: 1px solid var(--border);
  border-radius: 6px;
  overflow: hidden;
}

.toggle-btn {
  padding: 0.3rem 0.85rem;
  border: none;
  background: var(--surface);
  font-size: var(--text-sm);
  font-weight: 600;
  cursor: pointer;
  color: var(--muted);
  transition: background 0.12s, color 0.12s;
}

.toggle-btn.active {
  background: var(--accent);
  color: #fff;
}

.toggle-btn:not(.active):hover {
  background: #f0f0f0;
}

.filter-select {
  padding: 0.3rem 0.6rem;
  border: 1px solid var(--border);
  border-radius: 6px;
  font-size: var(--text-sm);
  background: var(--surface);
  cursor: pointer;
}

.date-range-box {
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1rem 1.25rem 1.25rem;
  margin-bottom: 1.25rem;
}

.date-range-labels {
  display: flex;
  justify-content: space-between;
  font-size: var(--text-xs);
  color: var(--muted);
  margin-bottom: 0.6rem;
}

.range-title {
  font-weight: 600;
  color: var(--text);
}

.chart-wrap {
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.25rem 1.25rem 1rem;
  height: 340px;
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
