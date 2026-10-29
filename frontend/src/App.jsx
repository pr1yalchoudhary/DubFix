import { useEffect, useRef, useState } from 'react'
import Icon from './Icon'
import AppHeader from './AppHeader'
import { request, uploadAudio, downloadAudio, setDemoAccessToken, initializeUsage, subscribeUsage } from './api'
import { stamp } from './WaveformEditor'
import { EMPTY_DELIVERY } from './DeliveryControls'
import EditorWorkspace from './EditorWorkspace'
import { sameSelection, validSelection, previewBlocker, previewKey } from './editorState'

const CONSENT = "I confirm that this is my voice or that I have the speaker's permission to use it for AI-generated speech."

export default function App() {
  const [usage, setUsage] = useState(null)
  useEffect(() => {
    const unsubscribe = subscribeUsage(setUsage)
    initializeUsage().catch(() => {})
    return unsubscribe
  }, [])
  const [session, setSession] = useState(null), [file, setFile] = useState(null), [consent, setConsent] = useState(false)
  const [busy, setBusy] = useState(''), [progress, setProgress] = useState(0), [error, setError] = useState('')
  const [region, setRegion] = useState({ start: 0, end: 3 }), [text, setText] = useState('')
  const [preview, setPreview] = useState(null), [version, setVersion] = useState('current'), [exported, setExported] = useState(false)
  const [previewError, setPreviewError] = useState('')
  const [dragging, setDragging] = useState(false), [notice, setNotice] = useState('')
  const [mode, setMode] = useState('correct'), [delivery, setDelivery] = useState({ ...EMPTY_DELIVERY })
  const [originalText, setOriginalText] = useState('')
  const [cleanup, setCleanup] = useState(null)
  const [selectionFinal, setSelectionFinal] = useState(true)
  const [transcription, setTranscription] = useState({ status: '', message: '' })
  const transcriptCache = useRef(new Map()), asrPending = useRef(new Map())
  const [asrRetry, setAsrRetry] = useState(0)
  useEffect(() => {
    transcriptCache.current.clear()
    setDelivery(value => ({ ...value, segment_text: '', translated_text: '' }))
    setTranscription({ status: '', message: '' })
  }, [session?.session_id, session?.revision])
  useEffect(() => {
    if (mode !== 'delivery' || !selectionFinal || !session || !validSelection(region, session.duration)) return
    const key = JSON.stringify([session.session_id, session.revision, region.start, region.end])
    let active = true
    setPreview(null)
    setDelivery(value => ({ ...value, segment_text: '', translated_text: '' }))
    if (transcriptCache.current.has(key)) {
      setDelivery(value => ({ ...value, segment_text: transcriptCache.current.get(key) }))
      setTranscription({ status: 'ready', message: 'Detected speech — review or edit the words below.' })
      return
    }
    setTranscription({ status: 'loading', message: 'Detecting speech in the selected segment…' })
    if (!asrPending.current.has(key)) {
      const pending = request('/api/transcribe', { session_id: session.session_id, revision: session.revision, ...region })
      asrPending.current.set(key, pending)
      pending.finally(() => asrPending.current.delete(key)).catch(() => {})
    }
    asrPending.current.get(key).then(result => {
      if (!active) return
      if (result.session_id !== session.session_id || result.revision !== session.revision || !sameSelection(result, region) || !result.text?.trim()) throw new Error('Speech detection returned an outdated or empty transcript.')
      transcriptCache.current.set(key, result.text)
      setDelivery(value => ({ ...value, segment_text: result.text }))
      setTranscription({ status: 'ready', message: 'Detected speech — review or edit the words below.' })
    }).catch(e => { if (active) setTranscription({ status: 'error', message: `Speech detection failed: ${e.message} You can enter the words manually below.` }) })
    return () => { active = false }
  }, [mode, selectionFinal, session?.session_id, session?.revision, region.start, region.end, asrRetry])
  const spokenText = mode === 'delivery' ? (delivery.language === 'original' ? delivery.segment_text : delivery.translated_text) : text
  function changeRegion(value, finalized = true) {
    setSelectionFinal(finalized)
    if (!sameSelection(value, region)) {
      setRegion(value); setPreview(null)
      setDelivery(previous => ({ ...previous, segment_text: '', translated_text: '' }))
      setTranscription({ status: '', message: '' })
    }
  }
  function choose(value) {
    setError('')
    if (!value) return
    if (!/\.(wav|mp3)$/i.test(value.name)) { setError('Please upload an MP3 or WAV recording.'); return }
    if (value.size > 25 * 1024 * 1024) { setError('Recording exceeds the 25 MB upload limit.'); return }
    setFile(value)
  }
  async function upload() {
    if (!file) { setError('Choose an MP3 or WAV recording.'); return }
    if (!consent) { setError('Confirm that you have permission to use this voice.'); return }
    setBusy('upload'); setError(''); setProgress(0)
    try {
      const uploaded = await uploadAudio(file, consent, setProgress)
      setRegion({ start: 0, end: Math.min(3, uploaded.duration) }); setSession(uploaded)
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  async function generate() {
    const reason = previewBlocker({ busy, region, session, spokenText, mode, language: delivery.language })
    if (reason) { setError(reason); return }
    if (mode === 'delivery' && (!selectionFinal || transcription.status === 'loading')) return
    setBusy('generate'); setError(''); setPreviewError(''); setNotice(''); setPreview(null)
    const requestKey = previewKey(session, region, mode, text, delivery, originalText)
    try {
      const generated = await request('/api/preview', { session_id: session.session_id, revision: session.revision, mode, ...region, replacement_text: spokenText, original_text: originalText.trim() || undefined,
        ...(mode === 'delivery' ? { mode, ...delivery } : {}) })
      if (!generated?.preview_id || !generated?.preview_url) throw new Error('The preview response did not include a playable clip. Generate a new preview before applying.')
      setPreview({ ...generated, request_key: requestKey })
      if (generated.voice_prepared) setSession(value => ({ ...value, voice_prepared: true, cleanup_available: false }))
    }
    catch (e) {
      const diagnostic = e.code ? ` [${e.code}]` : ''
      const message = `Preview failed${e.status ? ` (HTTP ${e.status})` : ''}: ${e.message}${diagnostic}`
      setError(message); setPreviewError(message)
    } finally { setBusy('') }
  }
  async function replace() {
    if (busy) return
    if (!preview?.preview_id || !preview?.preview_url) { setError('Generate a valid preview before applying the replacement.'); return }
    if (preview.request_key !== previewKey(session, region, mode, text, delivery, originalText)) { setPreview(null); setError('This preview no longer matches your selection, mode or recording. Generate a new preview.'); return }
    setBusy('replace'); setError('')
    try {
      const updated = await request('/api/replace', { session_id: session.session_id, preview_id: preview.preview_id, revision: session.revision, mode, ...region })
      setSession(updated)
      setRegion({ start: NaN, end: NaN }); setOriginalText('')
      setPreview(null); setVersion('current'); setNotice('Replacement applied. Previous edits are preserved. Select a new segment in the updated waveform for your next edit, or compare and export below.')
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  async function undo(action = 'undo') {
    if (busy) return
    setBusy(action); setError('')
    try {
      setSession(await request(`/api/${action}/${session.session_id}`, { revision: session.revision }))
      setRegion({ start: NaN, end: NaN }); setPreview(null); setPreviewError(''); setVersion('current'); setOriginalText('')
      setNotice(action === 'redo' ? 'Edit restored. Select a segment in the updated recording.' : 'Last edit undone. Select a new segment using the updated timestamps.')
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  async function previewCleanup() {
    if (busy) return
    setBusy('cleanup'); setError('')
    try { setCleanup(await request(`/api/cleanup/${session.session_id}`, { revision: session.revision })) }
    catch (e) { setError(e.message) } finally { setBusy('') }
  }
  async function chooseCleanup(accept) {
    if (busy || !cleanup) return
    setBusy('cleanup'); setError('')
    try {
      setSession(await request(`/api/cleanup/${session.session_id}/choice`, { revision: session.revision, cleanup_id: cleanup.cleanup_id, accept }))
      setCleanup(null); if (accept) setPreview(null)
      setNotice(accept ? 'Cleanup accepted for voice setup only. Your Original and Current recordings are unchanged.' : 'Cleanup rejected. The original voice sample will be used.')
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  async function download() {
    setBusy('export'); setError('')
    try {
      const blob = await downloadAudio(`/api/export/${session.session_id}`)
      const url = URL.createObjectURL(blob), link = document.createElement('a')
      link.href = url; link.download = 'tweeq-corrected.mp3'; link.click()
      setTimeout(() => URL.revokeObjectURL(url), 30000); setExported(true)
    } catch (e) { setError(e.message) } finally { setBusy('') }
  }
  function reset() { setCleanup(null); setSession(null); setPreview(null); setPreviewError(''); setFile(null); setConsent(false); setText(''); setOriginalText(''); setError(''); setNotice(''); setExported(false); setVersion('current'); setMode('correct'); setDelivery({ ...EMPTY_DELIVERY }) }
  const locked = !!busy
  return <div className="app-shell">
    <AppHeader recordingName={session?.name} busy={locked} canExport={!!(session?.edit_count ?? session?.revision)} onNew={reset} onExport={download}/>
    <main>
      {usage?.mode === 'public' && <section className="panel" aria-label="Free AI usage" role="status">
        <strong>{usage.unavailable ? 'Public AI temporarily unavailable' : `${usage.remaining} free AI uses remaining`}</strong>
        {!usage.unavailable && <p>{usage.global_remaining} public AI uses left in total. {usage.remaining === 0 && 'Your free allowance has been reached. Playback, Undo/Redo and export remain available.'}</p>}
        <p>{usage.message}</p>
        <small>Anonymous sessions and network limits reduce abuse; they do not identify individual people.</small>
        {usage.unavailable && <button className="secondary" onClick={() => initializeUsage().catch(() => {})}>Check availability</button>}
      </section>}
      {usage?.mode === 'demo' && <details className="panel"><summary>Demo access</summary>
        <label>Demo access code <input type="password" autoComplete="off" spellCheck={false} aria-label="Demo access code" onChange={e => setDemoAccessToken(e.target.value)}/></label>
        <p>Required for AI previews and speech detection. Kept only until this page is reloaded. After entering your code, retry speech detection or generate a preview.</p>
      </details>}
      {error && <div role="alert" className="alert"><span>{error}</span><button className="quiet" onClick={() => setError('')} aria-label="Dismiss error">×</button></div>}
      {notice && !exported && <div role="status" className="success">{notice}</div>}
      {!session ? <section className="upload-screen">
        <div className="upload-card">
          <div className={`drop-zone ${dragging ? 'dragging' : ''}`} onDragOver={e => { e.preventDefault(); setDragging(true) }} onDragLeave={() => setDragging(false)} onDrop={e => { e.preventDefault(); setDragging(false); if (!locked) choose(e.dataTransfer.files[0]) }}>
            <div className="upload-icon"><Icon name="waveform" size={36}/></div>
            <h1>Upload your recording</h1><p>Choose an audio file to get started.</p>
            <label className={`button primary ${locked ? 'disabled' : ''}`}><Icon name="folder"/>Choose File<input disabled={locked} type="file" accept=".mp3,.wav,audio/mpeg,audio/wav" onChange={e => choose(e.target.files[0])}/></label>
            <small>or drag and drop · MP3 or WAV · Up to 25 MB</small>
          </div>
          {file && <div className="selected-file"><Icon name="waveform"/><span><strong>{file.name}</strong><small>{(file.size / 1024 / 1024).toFixed(2)} MB · Ready to open</small></span></div>}
          <label className="consent"><input type="checkbox" checked={consent} disabled={locked} onChange={e => setConsent(e.target.checked)}/><span>{CONSENT}</span></label>
          <p className="privacy-note">Authorized voice samples and text are sent to Fish Audio when you use AI editing. Requests may consume credits.</p>
          {file && <button className="primary wide" disabled={locked || !consent} onClick={upload}>{busy === 'upload' ? progress < 100 ? `Uploading… ${progress}%` : 'Preparing your recording…' : 'Open recording'}<Icon name="arrow"/></button>}
          {busy === 'upload' && <progress value={progress} max="100" aria-label="Upload progress"/>}
        </div><p className="original-note"><Icon name="shield" size={16}/>Your original recording stays untouched.</p>
      </section> : exported ? <section className="export-screen panel">
        <div className="check"><Icon name="check" size={30}/></div><p className="eyebrow">GOOD WORDS. GREAT TAKE.</p><h1>Your recording,<br/><em>corrected.</em></h1>
        <p>Your MP3 is ready, and the download has started.<br/>Your original recording is still unchanged.</p>
        <div className="export-meta">MP3 · 192 kbps · {stamp(session.duration)}</div>
        <button className="primary" disabled={locked} onClick={download}>{busy === 'export' ? 'Exporting…' : '↓ Download again'}</button>
        <button className="secondary" disabled={locked} onClick={() => setExported(false)}>Back to editor</button>
        <button className="quiet" disabled={locked} onClick={reset}>Start over</button>
      </section> : <>
        <EditorWorkspace cleanup={cleanup} previewCleanup={previewCleanup} chooseCleanup={chooseCleanup} session={session} region={region} changeRegion={changeRegion}
          text={text} originalText={originalText} changeOriginalText={value => { setOriginalText(value); setPreview(null) }}
          changeText={value => { setText(value); setPreview(null) }} mode={mode}
          changeMode={value => { if (value !== mode) { setMode(value); setPreview(null); setError('') } }}
          delivery={delivery} changeDelivery={value => {
            if (validSelection(region, session.duration)) transcriptCache.current.set(JSON.stringify([session.session_id, session.revision, region.start, region.end]), value.segment_text)
            setDelivery(value); setPreview(null)
          }} preview={preview}
          transcription={transcription} retryTranscription={() => setAsrRetry(n => n + 1)} selectionFinal={selectionFinal}
          generate={generate} replace={replace} undo={() => undo()} redo={() => undo('redo')} download={download} busy={busy} error={setError} previewError={previewError}
          previewPlaybackFailed={() => { const message = 'The generated preview audio could not load. Check the backend connection and session, then generate a new preview.'; setPreview(null); setPreviewError(message); setError(message) }}
          version={version} setVersion={setVersion} reset={reset}/>

      </>}
    </main><footer><span>Tweeq <span className="muted">/ One mistake shouldn't mean another take.</span></span><span className="muted">Local editing. Your voice, with permission.</span></footer>
  </div>
}
