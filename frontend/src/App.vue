<script setup>
import { ref, computed, provide, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { CONFIG } from './config.js'
import { apiFetch } from './composables/useApi.js'
import { getToken, logout, exchangeCode, getUser } from './composables/useAuth.js'

provide('apiFetch', apiFetch)
provide('CONFIG', CONFIG)

const router = useRouter()
const ready = ref(false)
const user = computed(() => getUser())
const showDropdown = ref(false)

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

function toggleDropdown() {
  showDropdown.value = !showDropdown.value
}

function closeDropdown(e) {
  if (!e.target.closest('.user-menu')) {
    showDropdown.value = false
  }
}

onMounted(() => document.addEventListener('click', closeDropdown))
onUnmounted(() => document.removeEventListener('click', closeDropdown))
</script>

<template>
  <div id="app">
    <header>
      <div class="header-top">
        <h1>Receipt Scanner</h1>
        <div v-if="ready" class="user-menu" @click.stop="toggleDropdown">
          <svg class="user-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
            <circle cx="12" cy="8" r="4"/>
            <path d="M4 20c0-4 3.6-7 8-7s8 3 8 7"/>
          </svg>
          <span v-if="user?.email" class="user-email">{{ user.email }}</span>
          <svg class="chevron" :class="{ open: showDropdown }" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <polyline points="6 9 12 15 18 9"/>
          </svg>
          <div v-if="showDropdown" class="dropdown">
            <button class="dropdown-item" @click="logout()">Sign out</button>
          </div>
        </div>
      </div>
      <nav v-if="ready" class="header-nav">
        <RouterLink to="/list" class="nav-link">List View</RouterLink>
        <RouterLink to="/graphs" class="nav-link">Graphs</RouterLink>
      </nav>
    </header>

    <main v-if="ready">
      <RouterView />
    </main>
  </div>
</template>

<style scoped>
header {
  display: flex;
  flex-direction: column;
  gap: 0;
  padding: 0 !important;
}

.header-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0.6rem 1.5rem;
  border-bottom: 1px solid var(--border);
}

.header-nav {
  display: flex;
  gap: 0.25rem;
  padding: 0.4rem 1.5rem;
  background: var(--surface);
  border-bottom: 1px solid var(--border);
}

.user-menu {
  position: relative;
  display: flex;
  align-items: center;
  gap: 0.4rem;
  cursor: pointer;
  padding: 0.3rem 0.5rem;
  border-radius: 6px;
  transition: background 0.15s;
  user-select: none;
}

.user-menu:hover {
  background: #e8eaed;
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

.chevron {
  width: 0.9rem;
  height: 0.9rem;
  color: var(--muted);
  transition: transform 0.15s;
  flex-shrink: 0;
}

.chevron.open {
  transform: rotate(180deg);
}

.dropdown {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 6px;
  box-shadow: var(--shadow);
  min-width: 8rem;
  z-index: 100;
}

.dropdown-item {
  display: block;
  width: 100%;
  padding: 0.55rem 1rem;
  font-size: var(--text-sm);
  text-align: left;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text);
  border-radius: 6px;
}

.dropdown-item:hover {
  background: #f0f0f0;
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
