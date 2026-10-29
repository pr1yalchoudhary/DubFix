import { apiUrl } from './api'
import { useEffect, useRef, useState } from 'react'
import DeliveryControls from './DeliveryControls'
import Icon from './Icon'
import { RecordingSurface, EditingFields, EditingModeControl, QualityDisclosure, ReplacementPreview, ComparisonExport, EditHistoryList } from './EditorSurfaces'
import WaveformEditor, { stamp } from './WaveformEditor'
import { previewBlocker, shortCorrection, previewKey, validSelection } from './editorState'

function StepHeading({ number, title, children, badge }) {
  return <div className="step-heading"><span className="step-number">{number}</span><div><h2>{title}</h2><p>{children}</p></div>{badge && <span className="pill">{badge}</span>}</div>
}

export default function EditorWorkspace({ cleanup, previewCleanup, chooseCleanup, session, region, changeRegion, text, changeText,
  originalText, changeOriginalText, mode, changeMode, delivery, changeDelivery, preview, generate, replace, undo, redo, transcription, retryTranscription, selectionFinal, download, busy, error, previewError, previewPlaybackFailed, version, setVersion, reset }) {
  const comparison = useRef(null), previewPlayer = useRef(null), cleanupOriginal = useRef(null), cleanupPreview = useRef(null)
  const [comparisonPlaying, setComparisonPlaying] = useState(false), [nativePlayback, setNativePlayback] = useState(0)
  const locked = !!busy
  const validPreview = !!(preview?.preview_id && preview?.preview_url && preview.request_key === previewKey(session, region, mode, text, delivery, originalText))
  const editCount = session.edit_count ?? session.revision
  useEffect(() => { setComparisonPlaying(false) }, [session.revision, version])
  const spokenText = mode === 'delivery' ? (delivery.language === 'original' ? delivery.segment_text : delivery.translated_text) : text
  const reason = mode === 'delivery' && (transcription?.status === 'loading' || selectionFinal === false) ? 'Finish selecting and wait for speech detection, or enter words after a detection failure.' : previewBlocker({ busy, region, session, spokenText, mode, language: delivery.language })
  const busyText = { upload: 'Preparing your recording…', cleanup: 'Preparing optional cleanup…', generate: !session.voice_prepared ? 'Preparing your voice and preview…' : mode === 'delivery' ? 'Generating performance…' : 'Generating replacement speech…', replace: 'Inserting the preview into your recording…', undo: 'Restoring the previous recording…', redo: 'Restoring the next recording…', export: 'Preparing your MP3 download…' }[busy]
  function stopOtherAudio(except) {
    for (const player of [comparison.current, previewPlayer.current, cleanupOriginal.current, cleanupPreview.current]) if (player && player !== except) player.pause()
    if (except) setNativePlayback(n => n + 1)
  }
  function selectVersion(next) {
    comparison.current?.pause(); setComparisonPlaying(false); setVersion(next)
  }
  // Presentation state only: the underlying region/revision/handlers are unchanged.
  const viewKey = `${session.session_id}:${session.revision}`
  const [selectedView, setSelectedView] = useState('')
  const showEditing = selectedView === viewKey
  const reviewVisible = !!(validPreview || busy === 'generate' || previewError)
  function selectRegion(value, finalized = true) {
    changeRegion(value, finalized)
    if (finalized && validSelection(value, session.duration)) setSelectedView(viewKey)
  }
  return <div className="workspace">
    {locked && <div className="busy-banner" role="status"><span className="spinner"/><strong>{busyText}</strong></div>}
    <RecordingSurface>
      <StepHeading number="1" title="Recording">Select a phrase in the waveform to make an edit.</StepHeading>
      <div className="recording-meta"><h1>{session.name}</h1><span>{stamp(session.duration)}{editCount ? ` · ${editCount} edit${editCount > 1 ? 's' : ''}` : ''}</span></div>
      <p className="field-help" role="status">{session.voice_error ? 'Voice setup needs a clearer recording.' : session.voice_prepared ? 'Voice ready.' : 'Ready to edit.'}</p>
      {session.voice_error && <p className="warning">{session.voice_error} You can still play your recording.</p>}
      {session.voice_status === 'configuration_required' && <p className="warning">Speech generation is not configured. Your recording and draft text remain available.</p>}
      <QualityDisclosure report={session.quality}/>
      {session.cleanup_available && !cleanup && <button className="secondary" disabled={locked} onClick={previewCleanup}>Compare gentle cleanup</button>}
      {session.cleanup_accepted && <p className="field-help">Cleanup accepted for voice setup. Original and Current remain unchanged.</p>}
      {cleanup && <div className="field-help" aria-label="Optional cleanup comparison"><p>Listen to both versions. Gentle cleanup may reduce steady noise, but can also affect speech. Nothing changes until you choose; this affects voice setup only.</p>
        <label>Original recording<audio ref={cleanupOriginal} onPlay={() => stopOtherAudio(cleanupOriginal.current)} controls src={apiUrl(`/api/audio/${session.session_id}?version=original`)} aria-label="Original for cleanup comparison"/></label>
        <label>Gentle cleanup<audio ref={cleanupPreview} onPlay={() => stopOtherAudio(cleanupPreview.current)} controls src={apiUrl(cleanup.cleaned_url)} aria-label="Gentle cleanup preview"/></label>
        {cleanup.error && <p role="alert">{cleanup.error}</p>}
        <button className="secondary" disabled={locked || !cleanup.can_accept || session.voice_prepared} onClick={() => chooseCleanup(true)}>Use cleanup for voice setup</button>
        <button className="quiet" disabled={locked} onClick={() => chooseCleanup(false)}>Keep original voice</button></div>}
      <WaveformEditor url={apiUrl(`/api/audio/${session.session_id}?version=current&revision=${session.revision}`)} duration={session.duration} region={region} onRegion={selectRegion} disabled={locked} onError={error} onPlay={() => stopOtherAudio()} pauseSignal={nativePlayback} undo={undo} redo={redo} canUndo={!!editCount} canRedo={!!session.can_redo}/>
    </RecordingSurface>
    {!showEditing && <div className="selection-prompt"><div><h2>Select a phrase to start editing</h2><p>Drag across the waveform, or adjust Start and End.</p></div>
      {validSelection(region, session.duration) && <button className="secondary" disabled={locked} onClick={() => selectRegion(region, true)}>Edit selection</button>}</div>}
    <EditingFields hidden={!showEditing}>
      <StepHeading number="2" title="What would you like to change?"></StepHeading>
      <EditingModeControl mode={mode} disabled={locked} onChange={changeMode}/>
      <div id="correction-fields" role="tabpanel" aria-labelledby={mode === 'delivery' ? 'delivery-tab' : 'correct-tab'}>
        <p className="mode-description">{mode === 'correct' ? 'Replace the selected words while keeping your voice.' : 'Keep your words. Choose a different delivery.'}</p>
        {mode === 'correct' ? <><label className="field-label" htmlFor="replacement">What should it say instead?</label>
          <textarea id="replacement" rows="4" maxLength={1000} placeholder="e.g. The conference is on April fifth." value={text} disabled={locked} onChange={e => changeText(e.target.value)}/>
          {shortCorrection(text) && <p className="field-help" role="note"><span aria-hidden="true">ⓘ </span><strong>Tip:</strong> For seamless edits, include a few words before and after the word you want to change.</p>}
          <small className="character-count">{text.length}/1,000</small></>
          : <><p role={transcription?.status === 'error' ? 'alert' : 'status'} className="field-help">{transcription?.message}</p>{transcription?.status === 'error' && <button className="secondary" disabled={locked} onClick={retryTranscription}>Retry speech detection</button>}<DeliveryControls detecting={transcription?.status === 'loading'} value={delivery} disabled={locked} onChange={changeDelivery}/></>}
      </div>
      <details className="history-words"><summary>Original words for history <span>optional</span></summary>
      <label className="field-label" htmlFor="original-phrase">Original selected words (optional, for history)</label>
      <input id="original-phrase" type="text" maxLength={1000} value={originalText} disabled={locked} onChange={e => changeOriginalText(e.target.value)} placeholder="e.g. We’re launching next Monday"/></details>
      <div className="generation-action"><button className="primary" disabled={!!reason} aria-describedby="preview-help" onClick={generate}>{busy === 'generate' ? <><span className="spinner"/>{mode === 'delivery' ? 'Generating performance…' : 'Generating replacement…'}</> : 'Generate Preview'}</button>
        <p className={reason ? 'action-help' : 'field-help'} id="preview-help" role="status">{reason || 'Ready to preview. Your recording stays unchanged until you insert the generated clip.'}</p>
      </div>
    </EditingFields>
    <ComparisonExport hidden={!showEditing && !editCount && !reviewVisible}>
      <StepHeading number="3" title="Preview and compare">Listen before you apply. Your original stays untouched.</StepHeading>
      <ReplacementPreview hidden={!reviewVisible}>
      <div className={`preview-box ${validPreview ? 'has-preview' : ''}`}><div className="preview-heading"><h3>Replacement preview</h3><button className="quiet" disabled={!!reason} onClick={generate}>Regenerate</button>{validPreview && <span className="pill">{Number.isFinite(preview.duration) ? `${preview.duration.toFixed(2)}s` : 'Ready'}{preview.mode === 'delivery' ? ' · Drama 3' : ''}</span>}</div>
        {validPreview ? <audio ref={previewPlayer} key={preview.preview_id} controls src={apiUrl(preview.preview_url)} aria-label="Generated replacement speech" onError={previewPlaybackFailed} onPlay={() => stopOtherAudio(previewPlayer.current)}/>
          : previewError ? <div className="warning" role="alert"><strong>{previewError}</strong><p>No playable replacement is available. Current is unchanged and Apply Edit is unavailable. Resolve the error, then try Generate Preview again.</p></div>
          : busy === 'generate' ? <p className="field-help" role="status">Generating the replacement clip. The player and Apply Edit will become available when generation succeeds.</p>
          : <p className="field-help">Generate a preview above to listen here. Changing the selection, text or mode clears an outdated preview.</p>}
        {validPreview && (preview.continuity_warnings || []).map((message, i) => <p key={i} className="field-help" role="note">{message}</p>)}
        {validPreview && Math.abs(preview.duration_change || 0) >= .1 && <p className="field-help">This preview changes the selected duration by {preview.duration_change > 0 ? '+' : ''}{preview.duration_change.toFixed(2)}s. Listen for pacing before applying.</p>}
        <div className="insert-row"><p className="field-help" id="apply-help">{busy === 'replace' ? 'Applying the saved clip. No speech is being regenerated.' : validPreview ? `Listen first, then apply this exact clip to ${stamp(region.start)}–${stamp(region.end)}. Previewing alone does not change Current.` : 'Apply Edit becomes available after a successful preview.'}</p>
          <button className="primary" disabled={locked || !validPreview} aria-describedby="apply-help" onClick={replace}><Icon name="check"/>{busy === 'replace' ? 'Applying replacement…' : 'Apply Edit'}</button></div>
      </div>
      <p className="privacy-note">Authorized voice samples and text are sent to Fish Audio when needed. Change Delivery also sends the selected segment for speech detection. Requests may consume API credits.</p>
      </ReplacementPreview>
      <div className="compare-export-grid"><div className="comparison-player"><div className="segmented" role="group" aria-label="Comparison recording">
        <button disabled={locked} aria-pressed={version === 'original'} className={version === 'original' ? 'selected' : ''} onClick={() => selectVersion('original')}>Original</button>
        <button disabled={locked} aria-pressed={version === 'current'} className={version === 'current' ? 'selected' : ''} onClick={() => selectVersion('current')}>Edited</button>
      </div><div className="comparison-label" aria-live="polite"><span className={comparisonPlaying ? 'playing-dot playing' : 'playing-dot'}/>{comparisonPlaying ? 'Playing' : 'Ready to play'}: <strong>{version === 'original' ? 'Original recording' : 'Current recording'}</strong><span>{stamp(version === 'original' ? session.original_duration : session.duration)}</span></div>
        <audio ref={comparison} key={`${version}-${session.revision}`} controls preload="metadata" aria-label={version === 'original' ? 'Original recording comparison' : 'Current recording comparison'} src={apiUrl(`/api/audio/${session.session_id}?version=${version}&revision=${session.revision}`)}
          onPlay={() => { setComparisonPlaying(true); stopOtherAudio(comparison.current) }} onPause={() => setComparisonPlaying(false)} onEnded={() => setComparisonPlaying(false)}/>
        <p className="field-help">Comparison changes only this player. Your waveform selection and draft text stay in place.</p></div>
        <div className="export-action"><span className="eyebrow">Export</span><h3>Save your recording</h3><p className="field-help">MP3 · 192 kbps · {stamp(session.duration)}</p>
          <button className="primary" disabled={locked || !editCount} aria-describedby="export-help" onClick={download}><Icon name="download"/>{busy === 'export' ? 'Preparing MP3…' : 'Download MP3'}</button>
          <p className="field-help" id="export-help">{locked ? 'Wait for the current request to finish before exporting.' : editCount ? 'Downloads all currently applied edits. Your original stays untouched.' : 'Apply an edit to enable download.'}</p>
        </div></div>
    </ComparisonExport>
    {(session.edit_history || []).length > 0 && <>
    <EditHistoryList>
      <p className="field-help">{editCount ? 'Each applied edit is included in Current and your MP3. Undo restores the preceding audio version.' : 'No edits are currently applied. Apply a preview to add an edit.'}</p>
      <ol className="edit-history">{(session.edit_history || []).map(item => <li key={item.number}><strong>Edit {item.number} — {item.mode === 'delivery' ? 'Change Delivery' : 'Correct Speech'}</strong><span className="pill">{item.status === 'applied' ? 'Applied' : 'Undone'}</span>
        <p>{item.original_text ? `${item.original_text} → ` : ''}{item.mode === 'delivery' ? item.direction || 'Natural delivery' : item.replacement_text}</p></li>)}</ol>
    </EditHistoryList>    </>}
  </div>
}
