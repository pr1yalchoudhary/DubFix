const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || '').trim().replace(/\/+$/, '')
let demoAccessToken = ''

export function setDemoAccessToken(value) { demoAccessToken = value.trim() }

export function apiUrl(path) {
  if (!path || /^(https?:|blob:|data:)/i.test(path)) return path
  return `${API_BASE_URL}${path.startsWith('/') ? path : '/' + path}`
}

async function perform(path, body, kind, timeoutMs) {
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeoutMs)
  try {
    let response
    try {
      const headers = body ? { 'Content-Type': 'application/json' } : {}
      if (demoAccessToken && ['/api/preview', '/api/transcribe'].includes(path)) headers.Authorization = `Bearer ${demoAccessToken}`
      response = await fetch(apiUrl(path), { signal: controller.signal, headers,
        ...(kind === 'blob' ? { cache: 'no-store' } : {}),
        ...(body ? { method: 'POST', body: JSON.stringify(body) } : {}) })
    } catch (error) {
      if (error.name === 'AbortError') throw error
      throw new Error('Cannot reach the backend. Check the server and API URL configuration, then try again.')
    }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}))
      const error = new Error(typeof data.detail === 'string' ? data.detail : 'The request failed. Please try again.')
      error.status = response.status
      error.code = data.error_code
      error.upstreamStatus = data.upstream_status
      throw error
    }
    return await (kind === 'blob' ? response.blob() : response.json())
  } catch (error) {
    if (error.name === 'AbortError' || controller.signal.aborted) throw new Error('The request timed out. Your text is saved. Check the backend before trying again.' + (path === '/api/preview' ? ' Generation may already have consumed credits.' : ''))
    if (error instanceof SyntaxError) throw new Error('The backend returned an unreadable response. Check the server, then try again. Your text is saved.')
    throw error
  } finally { clearTimeout(timer) }
}

export const request = (path, body) => perform(path, body, 'json', 150000)
export const downloadAudio = path => perform(path, undefined, 'blob', 90000)

export function uploadAudio(file, consent, progress) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest()
    xhr.open('POST', apiUrl('/api/upload'))
    xhr.timeout = 150000
    xhr.upload.onprogress = event => { if (event.lengthComputable) progress(Math.round(event.loaded / event.total * 100)) }
    xhr.onerror = () => reject(new Error('Cannot reach the backend. Check the server and API URL configuration.'))
    xhr.ontimeout = () => reject(new Error('Upload timed out. Try a smaller recording.'))
    xhr.onload = () => {
      let data
      try { data = JSON.parse(xhr.responseText) } catch { reject(new Error('The backend returned an invalid response.')); return }
      if (xhr.status >= 200 && xhr.status < 300) resolve(data)
      else reject(new Error(data.detail || 'Upload failed. Please try again.'))
    }
    const form = new FormData()
    form.append('file', file); form.append('consent', String(consent)); xhr.send(form)
  })
}
