import { CONFIG } from '../config.js'

export function getToken() {
  return sessionStorage.getItem('id_token')
}

export function getUser() {
  const token = getToken()
  if (!token) return null
  try {
    const payload = token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')
    const claims = JSON.parse(atob(payload))
    return { email: claims.email || null, sub: claims.sub || null }
  } catch {
    return null
  }
}

export function logout() {
  sessionStorage.clear()
  const logoutUrl =
    CONFIG.cognitoLoginUrl.replace('/login?', '/logout?') +
    `&logout_uri=${encodeURIComponent(CONFIG.redirectUri.replace('/callback', '/'))}`
  window.location.href = logoutUrl
}

export async function exchangeCode(code) {
  const params = new URLSearchParams({
    grant_type:   'authorization_code',
    client_id:    CONFIG.cognitoClientId,
    code,
    redirect_uri: CONFIG.redirectUri,
  })
  const resp = await fetch(CONFIG.cognitoTokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  })
  if (!resp.ok) throw new Error(`Token exchange failed: ${resp.status}`)
  const data = await resp.json()
  sessionStorage.setItem('id_token', data.id_token)
  sessionStorage.setItem('access_token', data.access_token)
  if (data.refresh_token) sessionStorage.setItem('refresh_token', data.refresh_token)
  history.replaceState({}, document.title, window.location.pathname)
}

export async function refreshTokens() {
  const refreshToken = sessionStorage.getItem('refresh_token')
  if (!refreshToken) throw new Error('No refresh token')
  const params = new URLSearchParams({
    grant_type:    'refresh_token',
    client_id:     CONFIG.cognitoClientId,
    refresh_token: refreshToken,
  })
  const resp = await fetch(CONFIG.cognitoTokenUrl, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: params.toString(),
  })
  if (!resp.ok) throw new Error(`Token refresh failed: ${resp.status}`)
  const data = await resp.json()
  sessionStorage.setItem('id_token', data.id_token)
  sessionStorage.setItem('access_token', data.access_token)
}
