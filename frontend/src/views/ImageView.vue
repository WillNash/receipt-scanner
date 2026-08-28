<script setup>
import { ref, computed } from 'vue'
import UploadSection from '../components/UploadSection.vue'
import StatusSection from '../components/StatusSection.vue'
import ResultsSection from '../components/ResultsSection.vue'
import HistorySection from '../components/HistorySection.vue'
import { getToken } from '../composables/useAuth.js'

const view = ref('upload')
const scanResults = ref([])
const statusText = ref('')
const abortController = ref(null)
const historyKey = ref(0)

const isAuthenticated = computed(() => !!getToken())

function onScanStarted({ count, controller }) {
  abortController.value = controller
  statusText.value = `Uploading ${count} receipt${count > 1 ? 's' : ''}…`
  view.value = 'status'
}

function onStatusUpdate(text) {
  statusText.value = text
}

function onScanComplete(results) {
  scanResults.value = results
  view.value = 'results'
  historyKey.value++
}

function onScanError() {
  view.value = 'upload'
}

function onCancel() {
  if (abortController.value) abortController.value.abort()
}

function onScanMore() {
  view.value = 'upload'
}
</script>

<template>
  <UploadSection
    v-show="view === 'upload'"
    @scan-started="onScanStarted"
    @status-update="onStatusUpdate"
    @scan-complete="onScanComplete"
    @scan-error="onScanError"
  />

  <StatusSection
    v-if="view === 'status'"
    :text="statusText"
    @cancel="onCancel"
  />

  <ResultsSection
    v-if="view === 'results'"
    :jobs="scanResults"
    @scan-more="onScanMore"
  />

  <HistorySection
    v-if="isAuthenticated"
    :key="historyKey"
  />
</template>
