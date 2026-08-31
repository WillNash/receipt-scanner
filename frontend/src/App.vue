<script setup>
import { ref, computed, provide, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { CONFIG } from './config.js'
import { apiFetch } from './composables/useApi.js'
import { getToken, logout, exchangeCode, getUser } from './composables/useAuth.js'

provide('apiFetch', apiFetch)
provide('CONFIG', CONFIG)

const router = useRouter()
const ready = ref(false)
const isAuthenticated = computed(() => !!getToken())
const user = computed(() => getUser())

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
        <RouterLink to="/graphs" class="nav-link">Graphs</RouterLink>
      </nav>
      <div v-if="ready" class="user-info">
        <svg class="user-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
          <circle cx="12" cy="8" r="4"/>
          <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
        </svg>
        <span v-if="user?.email" class="user-email">{{ user.email }}</span>
        <button class="btn btn-secondary signout-btn" @click="handleLogout">Sign out</button>
      </div>
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
  margin-right: auto;
}

.user-info {
  display: flex;
  align-items: center;
  gap: 0.5rem;
  flex-shrink: 0;
}

.user-icon {
  width: 1.2rem;
  height: 1.2rem;
  color: var(--muted);
  flex-shrink: 0;
}

.user-email {
  font-size: var(--text-xs);
  color: var(--muted);
  max-width: 14rem;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.signout-btn {
  font-size: var(--text-xs);
  padding: 0.3rem 0.7rem;
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
