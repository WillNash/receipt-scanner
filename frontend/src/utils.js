export function formatDate(dateStr) {
  if (!dateStr) return ''
  const d = new Date(dateStr)
  return isNaN(d.getTime()) ? dateStr : d.toLocaleDateString()
}

export function apiErrorMessage(status) {
  if (status === 401 || status === 403) return 'Your session has expired — sign in again.'
  if (status === 429) return 'Upload limit reached. Try again tomorrow.'
  if (status >= 500) return 'Something went wrong on our end. Try again in a moment.'
  return `Unexpected error (${status}).`
}
