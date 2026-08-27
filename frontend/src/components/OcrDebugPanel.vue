<script setup>
import { ref, computed, onMounted } from 'vue'

const props = defineProps({
  url: {
    type: String,
    required: true,
  },
  jobId: {
    type: String,
    default: '',
  },
})

const data = ref(null)
const loading = ref(true)
const error = ref(false)

const deskewText = computed(() => {
  if (!data.value) return ''
  const deskew = data.value.deskew
  if (!deskew) return 'Deskew: no data (scan predates this feature)'

  const angle = deskew.angle_deg != null
    ? `${deskew.angle_deg.toFixed(2)}°`
    : 'insufficient lines for detection'

  let applied
  if (deskew.applied) {
    const snap = deskew.correction_deg != null ? ` → snapped to ${deskew.correction_deg}°` : ''
    applied = `corrected${snap}`
  } else if (deskew.angle_deg == null) {
    applied = 'insufficient lines for detection'
  } else {
    const absAngle = Math.abs(deskew.angle_deg)
    if (absAngle < deskew.threshold_deg) {
      applied = `below threshold (±${deskew.threshold_deg}°), no correction`
    } else {
      applied = 'outside correction range — no correction'
    }
  }
  return `Deskew: ${angle} — ${applied}`
})

const deskewClass = computed(() => {
  if (!data.value) return 'debug-deskew--ok'
  const deskew = data.value.deskew
  return deskew && deskew.applied ? 'debug-deskew--corrected' : 'debug-deskew--ok'
})

const rowGroupingText = computed(() => {
  if (!data.value || !data.value.row_grouping) return null
  const rg = data.value.row_grouping
  const lhPct = (rg.line_height * 100).toFixed(2)
  const stPct = (rg.step_tol * 100).toFixed(2)
  return `Row grouping: line height ${lhPct}%  step tolerance ${stPct}%`
})

const blocks = computed(() => data.value?.blocks || [])
const words  = computed(() => data.value?.words  || [])
const lines  = computed(() => data.value?.lines  || [])

const blocksHeading = computed(() => {
  if (!blocks.value.length) return ''
  const rowCount = blocks.value[blocks.value.length - 1].row + 1
  return `Textract blocks — ${blocks.value.length} blocks → ${rowCount} rows`
})

const wordsHeading = computed(() =>
  words.value.length ? `Textract words — ${words.value.length} words` : ''
)

// Build display rows: interleave entries with separator markers between rows
function toDisplayRows(items) {
  const rows = []
  let lastRow = -1
  for (const item of items) {
    if (item.row !== lastRow && lastRow !== -1) rows.push({ isSep: true })
    lastRow = item.row
    rows.push({ isSep: false, item })
  }
  return rows
}

const blockDisplayRows = computed(() => toDisplayRows(blocks.value))
const wordDisplayRows  = computed(() => toDisplayRows(words.value))

onMounted(async () => {
  try {
    const resp = await fetch(props.url)
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    data.value = await resp.json()
  } catch (err) {
    console.error('OCR debug load failed:', err)
    error.value = true
  } finally {
    loading.value = false
  }
})

async function downloadTextractJson() {
  const resp = await fetch(props.url)
  const blob = await resp.blob()
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `textract_${(props.jobId || 'unknown').slice(0, 8)}.json`
  a.click()
  URL.revokeObjectURL(url)
}

function downloadTestFixture() {
  const wordList = data.value?.words || []
  const lineList = data.value?.lines || []

  const maxTextLen = Math.max(...wordList.map(w => w.text.length), 0)

  const wordLines = wordList.map(w => {
    const escaped = w.text.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
    const topPct = (w.top * 100).toFixed(1)
    const leftPct = Math.round(w.left * 100)
    const pad = ' '.repeat(maxTextLen - w.text.length)
    return `    _word("${escaped}",${pad}  ${topPct.padStart(5)},  ${String(leftPct).padStart(2)}),`
  })

  const expectedLines = lineList.map(l => {
    const escaped = l.replace(/\\/g, '\\\\').replace(/"/g, '\\"')
    return `    "${escaped}",`
  })

  const shortId = (props.jobId || 'unknown').slice(0, 8)
  const rowCount = lineList.length

  const content = [
    `# ${wordList.length} words → ${rowCount} rows`,
    `# job_id: ${props.jobId || 'unknown'}`,
    ``,
    `WORDS = [`,
    ...wordLines,
    `]`,
    ``,
    `EXPECTED = [`,
    ...expectedLines,
    `]`,
  ].join('\n')

  const blob = new Blob([content], { type: 'text/x-python' })
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = `test_fixture_${shortId}.py`
  a.click()
  URL.revokeObjectURL(url)
}
</script>

<template>
  <div class="ocr-debug-panel">
    <div v-if="loading" class="debug-deskew-row debug-deskew--ok">Loading…</div>
    <div v-else-if="error" class="debug-deskew-row debug-deskew--ok">Failed to load OCR debug data.</div>
    <template v-else>
      <!-- Deskew row -->
      <div class="debug-deskew-row" :class="deskewClass">{{ deskewText }}</div>

      <!-- Row grouping calibration row -->
      <div v-if="rowGroupingText" class="debug-deskew-row debug-deskew--ok">
        {{ rowGroupingText }}
      </div>

      <!-- Blocks table -->
      <template v-if="blocks.length">
        <div class="debug-lines-heading">{{ blocksHeading }}</div>
        <table class="debug-blocks-table">
          <tbody>
            <template v-for="(row, idx) in blockDisplayRows" :key="idx">
              <tr v-if="row.isSep" class="debug-row-sep"><td colspan="3"></td></tr>
              <tr v-else :class="{ 'debug-block--low-conf': row.item.confidence < 85 }">
                <td class="debug-block-conf">{{ row.item.confidence.toFixed(0) }}%</td>
                <td class="debug-block-text">{{ row.item.text }}</td>
                <td class="debug-block-pos">
                  ↕{{ (row.item.top * 100).toFixed(1) }}% ←{{ Math.round(row.item.left * 100) }}%
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </template>

      <!-- Words table -->
      <template v-if="words.length">
        <div class="debug-lines-heading" style="margin-top:0.6rem">{{ wordsHeading }}</div>
        <table class="debug-blocks-table">
          <tbody>
            <template v-for="(row, idx) in wordDisplayRows" :key="idx">
              <tr v-if="row.isSep" class="debug-row-sep"><td colspan="3"></td></tr>
              <tr v-else :class="{ 'debug-block--low-conf': row.item.confidence < 85 }">
                <td class="debug-block-conf">{{ row.item.confidence.toFixed(0) }}%</td>
                <td class="debug-block-text">{{ row.item.text }}</td>
                <td class="debug-block-pos">
                  ↕{{ (row.item.top * 100).toFixed(1) }}% ←{{ Math.round(row.item.left * 100) }}%
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </template>

      <!-- Merged lines -->
      <template v-if="lines.length">
        <div class="debug-lines-heading" style="margin-top:0.6rem">
          Merged text sent to Claude ({{ lines.length }} lines)
        </div>
        <ol class="debug-lines">
          <li v-for="(line, i) in lines" :key="i">{{ line }}</li>
        </ol>
      </template>

      <!-- Download test fixture -->
      <button class="btn btn-secondary" style="margin-top:0.75rem;font-size:0.75rem;" @click="downloadTextractJson">
        Download textract JSON
      </button>
      <button class="btn btn-secondary" style="margin-top:0.75rem;font-size:0.75rem;margin-left:0.5rem;" @click="downloadTestFixture">
        Download test fixture (.py)
      </button>
    </template>
  </div>
</template>
