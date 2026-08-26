import { getToken, logout, refreshTokens } from './useAuth.js'

export async function apiFetch(url, options = {}) {
  const authHeaders = { Authorization: `Bearer ${getToken()}` }
  const resp = await fetch(url, {
    ...options,
    headers: { ...authHeaders, ...options.headers },
  })
  if (resp.status !== 401) return resp
  try {
    await refreshTokens()
  } catch (_) {
    logout()
    return resp
  }
  const retryHeaders = { Authorization: `Bearer ${getToken()}` }
  return fetch(url, {
    ...options,
    headers: { ...retryHeaders, ...options.headers },
  })
}
