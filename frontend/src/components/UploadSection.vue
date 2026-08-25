<script setup>
import { ref, inject } from 'vue'
import { apiErrorMessage } from '../utils.js'

const apiFetch = inject('apiFetch')
const CONFIG = inject('CONFIG')

const emit = defineEmits(['scan-started', 'status-update', 'scan-complete', 'scan-error'])

const MAX_FILE_BYTES = 20 * 1024 * 1024
const MAX_POLLS = 60
const POLL_INTERVAL_MS = 3000

const selectedFiles = ref([])
const error = ref('')
const dropSub = ref('JPEG or PNG · up to 20 MB each')
const isDragOver = ref(false)

async function selectFiles(files) {
  error.value = ''
  const fileArray = Array.from(files)
  const errors = []
  for (const file of fileArray) {
    if (!['image/jpeg', 'image/png'].includes(file.type)) {
      errors.push(`${file.name}: only JPEG and PNG are supported.`)
      continue
    }
    if (file.size > MAX_FILE_BYTES) {
      errors.push(`${file.name} exceeds 20 MB.`)
      continue
    }
    if (selectedFiles.value.find(s => s.name === file.name && s.size === file.size)) {
      errors.push(`${file.name} is already in the queue.`)
    } else {
      selectedFiles.value.push(file)
    }
  }
  if (errors.length) {
    error.value = errors.length === 1 ? errors[0] : errors.join('\n')
  }
}

function removeFile(index) {
  selectedFiles.value.splice(index, 1)
}

function clearQueue() {
  selectedFiles.value = []
  error.value = ''
}

function onFileInputChange(e) {
  selectFiles(Array.from(e.target.files))
  e.target.value = ''
}

function onDrop(e) {
  isDragOver.value = false
  selectFiles(Array.from(e.dataTransfer.files))
}

function onDropZoneClick() {
  document.getElementById('file-input-vue').click()
}

function onDropZoneKeydown(e) {
  if (e.key === 'Enter' || e.key === ' ') {
    document.getElementById('file-input-vue').click()
  }
}

async function pollUntilDone(jobId, signal, count = 0) {
  if (signal && signal.aborted) return { jobId, status: 'CANCELLED' }
  if (count >= MAX_POLLS) return { jobId, status: 'FAILED', reason: 'timeout' }
  try {
    const resp = await apiFetch(`${CONFIG.apiBaseUrl}/jobs/${jobId}`, { signal })
    if (!resp.ok) throw new Error(`HTTP ${resp.status}`)
    const job = await resp.json()
    if (job.status === 'COMPLETE' || job.status === 'FAILED' || job.status === 'DUPLICATE') return job
  } catch (err) {
    if (err.name === 'AbortError') return { jobId, status: 'CANCELLED' }
    console.error(`Poll error for ${jobId}:`, err)
  }
  await new Promise(res => {
    const t = setTimeout(res, POLL_INTERVAL_MS)
    if (signal) signal.addEventListener('abort', () => { clearTimeout(t); res() }, { once: true })
  })
  return pollUntilDone(jobId, signal, count + 1)
}

async function handleUpload() {
  if (selectedFiles.value.length === 0) return
  error.value = ''

  const filesToProcess = [...selectedFiles.value]
  selectedFiles.value = []

  const count = filesToProcess.length
  const controller = new AbortController()
  const { signal } = controller

  emit('scan-started', { count, controller })

  try {
    // Step 1 — get presigned URLs in parallel
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

    // Step 2 — PUT files to S3 in parallel
    emit('status-update', 'Uploading images…')
    await Promise.all(
      filesToProcess.map((file, i) =>
        fetch(urlResults[i].uploadUrl, {
          method: 'PUT',
          headers: { 'Content-Type': file.type },
          body: file,
        }).then(r => {
          if (!r.ok) throw new Error(`S3 upload failed for ${file.name}: ${r.status}`)
        })
      )
    )

    // Step 3 — poll all jobs in parallel (cancellable)
    const jobIds = urlResults.map(r => r.jobId)
    emit('status-update', `Scanning ${jobIds.length} receipt${jobIds.length > 1 ? 's' : ''}…`)
    const results = await Promise.all(jobIds.map(id => pollUntilDone(id, signal)))

    if (signal.aborted) {
      selectedFiles.value = filesToProcess
      return
    }

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
        <p class="drop-sub">{{ dropSub }}</p>
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
        <button
          class="queue-remove"
          :aria-label="`Remove ${file.name}`"
          @click="removeFile(i)"
        >✕</button>
      </li>
    </ul>

    <div v-if="selectedFiles.length > 0" class="scan-controls">
      <button class="btn btn-primary" @click="handleUpload">Scan receipts</button>
      <button class="btn btn-secondary" @click="clearQueue">Clear</button>
    </div>

    <p v-if="error" class="error-text">{{ error }}</p>
  </section>
</template>
