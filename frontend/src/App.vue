<script setup>
import { ref, computed, provide, onMounted } from 'vue'
import { CONFIG } from './config.js'
import { apiFetch } from './composables/useApi.js'
import { getToken, logout, exchangeCode } from './composables/useAuth.js'
import UploadSection from './components/UploadSection.vue'
import StatusSection from './components/StatusSection.vue'
import ResultsSection from './components/ResultsSection.vue'
import HistorySection from './components/HistorySection.vue'

// Provide shared dependencies to all descendants
provide('apiFetch', apiFetch)
provide('CONFIG', CONFIG)

const view = ref('loading')
const scanResults = ref([])
const statusText = ref('')
const abortController = ref(null)
const historyKey = ref(0)

const isAuthenticated = computed(() => !!getToken())

onMounted(async () => {
  const token = getToken()
  const code = new URLSearchParams(window.location.search).get('code')

  if (token) {
    view.value = 'upload'
    return
  }

  if (code) {
    try {
      await exchangeCode(code)
      view.value = 'upload'
    } catch (err) {
      console.error('Token exchange error:', err)
      window.location.href = CONFIG.cognitoLoginUrl
    }
    return
  }

  window.location.href = CONFIG.cognitoLoginUrl
})

function handleLogout() {
  logout()
}

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

function onScanError({ files, message }) {
  view.value = 'upload'
}

function onCancel() {
  if (abortController.value) {
    abortController.value.abort()
  }
}

function onScanMore() {
  view.value = 'upload'
}

function onHistoryRefresh() {
  historyKey.value++
}
</script>

<template>
  <div id="app">
    <header>
      <h1>Receipt Scanner</h1>
      <button v-if="isAuthenticated" class="btn btn-secondary" @click="handleLogout">Sign out</button>
    </header>

    <main>
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
        @saved="onHistoryRefresh"
      />
    </main>
  </div>
</template>
