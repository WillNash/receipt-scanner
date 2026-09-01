<script setup>
import { ref, inject, nextTick, onBeforeUnmount, computed } from 'vue'
import Cropper from 'cropperjs'
import 'cropperjs/dist/cropper.css'
import { apiErrorMessage } from '../utils.js'

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')

const emit = defineEmits(['scan-started', 'status-update', 'scan-complete', 'scan-error'])

const MAX_FILE_BYTES = 20 * 1024 * 1024
const CROP_LIMIT = 9 * 1024 * 1024
const MAX_POLLS = 60
const POLL_INTERVAL_MS = 3000

// Normal upload state
const selectedFiles = ref([])
const error = ref('')
const isDragOver = ref(false)

// Large file crop flow
const pendingLargeFile = ref(null)  // { file: File, objectUrl: string }
const cropMode = ref(null)          // null | 'choice' | 'manual'
const cropImgEl = ref(null)
const cropperInstance = ref(null)
const croppedSizeBytes = ref(null)
const cropError = ref('')
const cropConfirming = ref(false)
let debounceTimer = null

function fmtMB(bytes) {
  return (bytes / 1024 / 1024).toFixed(1) + ' MB'
}

const cropSizeClass = computed(() => {
  if (croppedSizeBytes.value === null) return ''
  if (croppedSizeBytes.value >= CROP_LIMIT) return 'size-over'
  if (croppedSizeBytes.value >= CROP_LIMIT * 0.8) return 'size-warn'
  return 'size-ok'
})

function _updateCropSize() {
  clearTimeout(debounceTimer)
  debounceTimer = setTimeout(() => {
    if (!cropperInstance.value || !pendingLargeFile.value || !cropImgEl.value) return
    const data = cropperInstance.value.getData(true)
    const img = cropImgEl.value
    const ratio = (data.width * data.height) / (img.naturalWidth * img.naturalHeight)
    croppedSizeBytes.value = Math.round(pendingLargeFile.value.file.size * ratio)
  }, 200)
}

function openManualCrop() {
  cropMode.value = 'manual'
  nextTick(() => {
    if (!cropImgEl.value) return
    if (cropperInstance.value) { cropperInstance.value.destroy(); cropperInstance.value = null }
    cropperInstance.value = new Cropper(cropImgEl.value, {
      viewMode: 1,
      autoCropArea: 0.85,
      zoomable: true,
      movable: true,
    })
    cropImgEl.value.addEventListener('ready', _updateCropSize)
    cropImgEl.value.addEventListener('cropend', _updateCropSize)
    cropImgEl.value.addEventListener('zoom', _updateCropSize)
  })
}

function chooseAutoCrop() {
  selectedFiles.value.push(pendingLargeFile.value.file)
  _closeCropPanel()
}

async function confirmManualCrop() {
  if (cropConfirming.value) return
  cropError.value = ''
  cropConfirming.value = true
  try {
    const canvas = cropperInstance.value.getCroppedCanvas({ maxWidth: 4096 })
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.92))
    if (!blob) throw new Error('Could not encode image')
    croppedSizeBytes.value = blob.size
    if (blob.size >= CROP_LIMIT) {
      cropError.value = `Cropped image is still ${fmtMB(blob.size)} — crop more tightly around the receipt.`
      return
    }
    const base = pendingLargeFile.value.file.name.replace(/\.[^.]+$/, '')
    selectedFiles.value.push(new File([blob], base + '_cropped.jpg', { type: 'image/jpeg' }))
    _closeCropPanel()
  } catch {
    cropError.value = 'Could not encode crop — try again.'
  } finally {
    cropConfirming.value = false
  }
}

function _closeCropPanel() {
  if (cropperInstance.value) { cropperInstance.value.destroy(); cropperInstance.value = null }
  if (pendingLargeFile.value?.objectUrl) URL.revokeObjectURL(pendingLargeFile.value.objectUrl)
  pendingLargeFile.value = null
  cropMode.value = null
  croppedSizeBytes.value = null
  cropError.value = ''
  clearTimeout(debounceTimer)
}

onBeforeUnmount(_closeCropPanel)

// File selection
function selectFiles(files) {
  error.value = ''
  const errors = []
  for (const file of Array.from(files)) {
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      errors.push(`${file.name}: only JPEG and PNG are supported.`)
      continue
    }
    if (file.size > MAX_FILE_BYTES) {
      errors.push(`${file.name} exceeds 20 MB.`)
      continue
    }
    if (selectedFiles.value.find(s => s.name === file.name && s.size === file.size && s.lastModified === file.lastModified)) {
      errors.push(`${file.name} is already in the queue.`)
      continue
    }
    if (file.size > CROP_LIMIT) {
      if (!cropMode.value) {
        pendingLargeFile.value = { file, objectUrl: URL.createObjectURL(file) }
        cropMode.value = 'choice'
      }
      continue
    }
    selectedFiles.value.push(file)
  }
  if (errors.length) error.value = errors.join('\n')
}

function removeFile(index) { selectedFiles.value.splice(index, 1) }
function clearQueue() { selectedFiles.value = []; error.value = '' }
function onFileInputChange(e) { selectFiles(Array.from(e.target.files)); e.target.value = '' }
function onDrop(e) { isDragOver.value = false; selectFiles(Array.from(e.dataTransfer.files)) }
function onDropZoneClick() { document.getElementById('file-input-vue').click() }
function onDropZoneKeydown(e) { if (e.key === 'Enter' || e.key === ' ') document.getElementById('file-input-vue').click() }

// Upload
async function pollUntilDone(jobId, signal) {
  for (let count = 0; count < MAX_POLLS; count++) {
    if (signal?.aborted) return { jobId, status: 'CANCELLED' }
    try {
      const resp = await apiFetch(`${CONFIG.apiBaseUrl}/jobs/${jobId}`, { signal })
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
      const job = await resp.json()
      if (['COMPLETE', 'FAILED', 'DUPLICATE'].includes(job.status)) return job
    } catch (err) {
      if (err.name === 'AbortError') return { jobId, status: 'CANCELLED' }
      console.error(`Poll error for ${jobId}:`, err)
    }
    await new Promise(res => {
      const t = setTimeout(res, POLL_INTERVAL_MS)
      signal?.addEventListener('abort', () => { clearTimeout(t); res() }, { once: true })
    })
  }
  return { jobId, status: 'FAILED', reason: 'timeout' }
}

async function handleUpload() {
  if (selectedFiles.value.length === 0) return
  error.value = ''
  const filesToProcess = [...selectedFiles.value]
  selectedFiles.value = []
  const controller = new AbortController()
  const { signal } = controller
  emit('scan-started', { count: filesToProcess.length, controller })
  try {
    const urlResults = await Promise.all(
      filesToProcess.map(file =>
        apiFetch(`${CONFIG.apiBaseUrl}/upload-url`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ contentType: file.type }),
        }).then(async r => {
          if (!r.ok) {
            const b = await r.json().catch(() => ({}))
            const err = new Error(b.error || apiErrorMessage(r.status))
            err.httpStatus = r.status
            throw err
          }
          return r.json()
        })
      )
    )
    emit('status-update', 'Uploading images…')
    await Promise.all(
      filesToProcess.map((file, i) =>
        fetch(urlResults[i].uploadUrl, {
          method: 'PUT',
          headers: { 'Content-Type': file.type },
          body: file,
        }).then(r => { if (!r.ok) throw new Error(`S3 upload failed for ${file.name}: ${r.status}`) })
      )
    )
    const jobIds = urlResults.map(r => r.jobId)
    emit('status-update', `Scanning ${jobIds.length} receipt${jobIds.length > 1 ? 's' : ''}…`)
    const results = await Promise.all(jobIds.map(id => pollUntilDone(id, signal)))
    if (signal.aborted) { selectedFiles.value = filesToProcess; return }
    emit('scan-complete', results)
  } catch (err) {
    console.error('Upload error:', err)
    selectedFiles.value = filesToProcess
    const knownStatus = err.httpStatus === 429 || err.httpStatus === 401 || err.httpStatus === 403
    error.value = knownStatus ? err.message : `Upload failed: ${err.message}`
    emit('scan-error', { files: filesToProcess, message: error.value })
  }
}
</script>

<template>
  <section>
    <!-- ===== LARGE FILE CROP PANEL ===== -->

    <!-- Choice screen -->
    <div v-if="cropMode === 'choice'" class="crop-panel">
      <p class="crop-panel-title">Image too large</p>
      <p class="crop-panel-sub">
        <strong>{{ pendingLargeFile.file.name }}</strong> is {{ fmtMB(pendingLargeFile.file.size) }} —
        images must be under 9 MB for scanning. Choose how to proceed:
      </p>

      <div class="crop-options">
        <button class="crop-option" @click="chooseAutoCrop">
          <span class="crop-option-label">Auto crop</span>
          <span class="crop-option-desc">
            Server crops the receipt automatically.<br>
            Works best on a dark background.
          </span>
        </button>
        <button class="crop-option" @click="openManualCrop">
          <span class="crop-option-label">Manual crop</span>
          <span class="crop-option-desc">
            Draw a crop box around the receipt.<br>
            Upload only what you select.
          </span>
        </button>
      </div>

      <button class="btn btn-secondary crop-cancel" @click="_closeCropPanel">Cancel</button>
    </div>

    <!-- Manual crop screen -->
    <div v-else-if="cropMode === 'manual'" class="crop-panel crop-panel--manual">
      <p class="crop-panel-title">Crop the receipt</p>
      <p class="crop-panel-sub">Drag the handles to frame just the receipt. Must be under 9 MB to continue.</p>

      <div class="crop-container">
        <img ref="cropImgEl" :src="pendingLargeFile.objectUrl" alt="" />
      </div>

      <div class="crop-footer">
        <div v-if="croppedSizeBytes !== null" class="size-indicator" :class="cropSizeClass">
          <span class="size-dot" />
          <span v-if="croppedSizeBytes >= CROP_LIMIT">
            Still {{ fmtMB(croppedSizeBytes) }} — crop more tightly
          </span>
          <span v-else>
            ~{{ fmtMB(croppedSizeBytes) }} — looks good
          </span>
        </div>
        <div v-else class="size-indicator">
          <span class="size-dot" />
          Adjust the crop box to see estimated size
        </div>

        <p v-if="cropError" class="crop-error">{{ cropError }}</p>

        <div class="crop-actions">
          <button class="btn btn-secondary" @click="_closeCropPanel">Cancel</button>
          <button
            class="btn btn-primary"
            :disabled="cropConfirming || croppedSizeBytes === null || croppedSizeBytes >= CROP_LIMIT"
            @click="confirmManualCrop"
          >{{ cropConfirming ? 'Encoding…' : 'Crop & add to queue' }}</button>
        </div>
      </div>
    </div>

    <!-- ===== NORMAL UPLOAD UI ===== -->
    <template v-else>
      <div
        class="drop-zone"
        :class="{ 'drag-over': isDragOver }"
        tabindex="0"
        aria-label="Drop receipt images here or click to select"
        @click="onDropZoneClick"
        @keydown="onDropZoneKeydown"
        @dragenter.prevent="isDragOver = true"
        @dragover.prevent="isDragOver = true"
        @dragleave="isDragOver = false"
        @drop.prevent="onDrop"
      >
        <div class="drop-zone-inner">
          <svg class="upload-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <path d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/>
          </svg>
          <p class="drop-hint">Drop receipt images here</p>
          <p class="drop-sub">JPEG or PNG · up to 20 MB each</p>
          <label class="btn btn-primary" for="file-input-vue" @click.stop>Choose files</label>
          <input
            id="file-input-vue"
            type="file"
            accept="image/jpeg,image/png"
            multiple
            style="display:none"
            @change="onFileInputChange"
          />
        </div>
      </div>

      <ul v-if="selectedFiles.length > 0" class="file-queue">
        <li v-for="(file, i) in selectedFiles" :key="file.name + file.size" class="queue-item">
          <span class="queue-name">{{ file.name }}</span>
          <span class="queue-size">{{ (file.size / 1024).toFixed(0) }} KB</span>
          <button class="queue-remove" :aria-label="`Remove ${file.name}`" @click="removeFile(i)">✕</button>
        </li>
      </ul>

      <div v-if="selectedFiles.length > 0" class="scan-controls">
        <button class="btn btn-primary" @click="handleUpload">Scan receipts</button>
        <button class="btn btn-secondary" @click="clearQueue">Clear</button>
      </div>
    </template>

    <p v-if="error" class="error-text">{{ error }}</p>
  </section>
</template>

<style scoped>
/* ---- Crop panel shared ---- */
.crop-panel {
  background: var(--surface);
  border-radius: var(--radius);
  box-shadow: var(--shadow);
  padding: 1.5rem;
}

.crop-panel-title {
  font-size: 1.1rem;
  font-weight: 700;
  margin: 0 0 0.4rem;
}

.crop-panel-sub {
  font-size: var(--text-sm);
  color: var(--muted);
  margin: 0 0 1.25rem;
}

/* ---- Choice options ---- */
.crop-options {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.75rem;
  margin-bottom: 1rem;
}

.crop-option {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  padding: 1rem 1.1rem;
  border: 1px solid var(--border);
  border-radius: var(--radius);
  background: var(--surface);
  cursor: pointer;
  text-align: left;
  transition: border-color 0.12s, background 0.12s;
}

.crop-option:hover {
  border-color: var(--accent);
  background: #f0f5ff;
}

.crop-option-label {
  font-size: var(--text-sm);
  font-weight: 700;
  color: var(--accent);
}

.crop-option-desc {
  font-size: var(--text-xs);
  color: var(--muted);
  line-height: 1.5;
}

.crop-cancel {
  font-size: var(--text-sm);
}

/* ---- Manual crop panel ---- */
.crop-panel--manual {
  padding: 1.25rem 1.25rem 1rem;
}

.crop-container {
  width: 100%;
  height: 420px;
  background: #111;
  border-radius: calc(var(--radius) - 2px);
  overflow: hidden;
  margin-bottom: 1rem;
}

.crop-container img {
  display: block;
  max-width: 100%;
}

.crop-footer {
  display: flex;
  flex-direction: column;
  gap: 0.6rem;
}

/* ---- Size indicator ---- */
.size-indicator {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  font-size: var(--text-sm);
  color: var(--muted);
}

.size-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #ccc;
  flex-shrink: 0;
}

.size-ok .size-dot  { background: #22c55e; }
.size-ok            { color: #166534; }
.size-warn .size-dot { background: #f59e0b; }
.size-warn           { color: #92400e; }
.size-over .size-dot { background: var(--danger); }
.size-over           { color: var(--danger); }

.crop-error {
  font-size: var(--text-sm);
  color: var(--danger);
  margin: 0;
}

.crop-actions {
  display: flex;
  gap: 0.6rem;
  justify-content: flex-end;
}
</style>
