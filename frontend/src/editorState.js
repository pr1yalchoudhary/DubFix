export function validSelection(region, duration) {
  return Number.isFinite(region.start) && Number.isFinite(region.end) && region.start >= 0 &&
    region.end <= duration && Math.round(region.start * 1000) < Math.round(region.end * 1000)
}

export function sameSelection(a, b) {
  return ['start', 'end'].every(key => Object.is(a[key], b[key]) || Math.abs(a[key] - b[key]) < .000001)
}

export function previewBlocker({ busy, region, session, spokenText, mode, language }) {
  if (busy) return 'Wait for the current request to finish. Your text is saved.'
  if (session.voice_error) return session.voice_error
  if (session.voice_status === 'configuration_required') return 'Speech generation is not configured. Ask the backend operator to configure Fish Audio, then upload again.'
  if (!Number.isFinite(region.start) && !Number.isFinite(region.end)) return 'Step 1: select a new segment in the current waveform before previewing your next edit.'
  if (!validSelection(region, session.duration)) return 'Step 1: set Start before End, within the recording, to select at least 0.001 seconds.'
  if (!spokenText.trim()) return mode === 'delivery'
    ? language === 'original' ? 'Step 2: enter the words you want to re-perform.' : 'Step 2: enter the text in your selected language.'
    : 'Step 2: enter the replacement text.'
  return ''
}

export function shortCorrection(text) {
  const words = text.trim().split(/\s+/u).filter(Boolean)
  return words.length > 0 && words.length <= 2
}

export function previewKey(session, region, mode, text, delivery, originalText = '') {
  return JSON.stringify({ session: session.session_id, revision: session.revision, referenceRevision: session.reference_revision || 0, start: region.start, end: region.end,
    mode, text: mode === 'correct' ? text : null, delivery: mode === 'delivery' ? delivery : null, originalText })
}
