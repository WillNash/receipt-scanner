<script setup>
import { ref, computed, provide, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { CONFIG } from './config.js'
import { apiFetch } from './composables/useApi.js'
import { getToken, logout, exchangeCode } from './composables/useAuth.js'

provide('apiFetch', apiFetch)
provide('CONFIG', CONFIG)

const router = useRouter()
const ready = ref(false)
const isAuthenticated = computed(() => !!getToken())

onMounted(async () => {
  const token = getToken()
  const code = new URLSearchParams(window.location.search).get('code')

  if (token) {
    ready.value = true
    return
  }

  if (code) {
    try {
      await exchangeCode(code)
      ready.value = true
      router.replace('/')
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
</script>

<template>
  <div id="app">
    <header>
      <h1>Receipt Scanner</h1>
      <nav v-if="ready" class="main-nav">
        <RouterLink to="/" class="nav-link">Image View</RouterLink>
        <RouterLink to="/list" class="nav-link">List View</RouterLink>
      </nav>
      <button v-if="ready" class="btn btn-secondary" @click="handleLogout">Sign out</button>
    </header>

    <main v-if="ready">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
.main-nav {
  display: flex;
  gap: 0.25rem;
}

.nav-link {
  padding: 0.4rem 0.85rem;
  border-radius: 6px;
  font-size: var(--text-sm);
  font-weight: 600;
  color: var(--text);
  text-decoration: none;
  transition: background 0.15s;
}

.nav-link:hover {
  background: #e8eaed;
}

.nav-link.router-link-active {
  background: var(--accent);
  color: #fff;
}
</style>
