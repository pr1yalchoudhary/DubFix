import { useEffect, useRef, useState } from 'react'
import WaveSurfer from 'wavesurfer.js'
import RegionsPlugin from 'wavesurfer.js/dist/plugins/regions.esm.js'
import TimelinePlugin from 'wavesurfer.js/dist/plugins/timeline.esm.js'
import Icon from './Icon'
import { sameSelection, validSelection } from './editorState'

export const stamp = n => {
  if (!Number.isFinite(n)) return '—'
  const cs = Math.round(Math.max(0, n) * 100)
  return `${Math.floor(cs / 6000).toString().padStart(2, '0')}:${((cs % 6000) / 100).toFixed(2).padStart(5, '0')}`
}
const inputValue = n => Number.isFinite(n) ? String(Math.round(n * 1000) / 1000) : ''

export default function WaveformEditor({ url, duration, region, onRegion, disabled, onError, onPlay, pauseSignal, undo, redo, canUndo, canRedo }) {
  const container = useRef(null), wave = useRef(null), regions = useRef(null), callback = useRef(onRegion)
  const errors = useRef(onError), playCallback = useRef(onPlay), selection = useRef(region), focused = useRef(null)
  const syncing = useRef(false), zoomRef = useRef(1)
  callback.current = onRegion; errors.current = onError; selection.current = region; playCallback.current = onPlay
  const [playing, setPlaying] = useState(false), [ready, setReady] = useState(false), [failed, setFailed] = useState(false)
  const [time, setTime] = useState(0), [zoom, setZoom] = useState(1)
  const [draft, setDraft] = useState({ start: inputValue(region.start), end: inputValue(region.end) })
  const valid = validSelection(region, duration)
  const emptySelection = !Number.isFinite(region.start) && !Number.isFinite(region.end)
  useEffect(() => {
    setDraft(previous => ({ start: focused.current === 'start' ? previous.start : inputValue(region.start),
      end: focused.current === 'end' ? previous.end : inputValue(region.end) }))
    const r = regions.current?.getRegions()[0]
    if (validSelection(region, duration) && ready) {
      syncing.current = true
      if (r && !sameSelection(r, region)) r.setOptions(region)
      else if (!r) regions.current?.addRegion({ ...region, color: 'rgba(176,128,255,.28)', minLength: .001, drag: true, resize: true })
      syncing.current = false
    } else if (!Number.isFinite(region.start) && !Number.isFinite(region.end)) {
      regions.current?.getRegions().forEach(item => item.remove())
    }
  }, [region.start, region.end, duration, ready])
  useEffect(() => {
    setReady(false); setFailed(false); setPlaying(false); setTime(0); setZoom(1); zoomRef.current = 1
    const plugin = RegionsPlugin.create()
    regions.current = plugin
    const timeline = TimelinePlugin.create({ height: 28, insertPosition: 'beforebegin', secondaryLabelOpacity: .65,
      style: { fontSize: '11px', color: '#c1b3d6' } })
    const ws = WaveSurfer.create({ container: container.current, url, height: 190, waveColor: '#77699a',
      progressColor: '#c5a7ff', cursorColor: '#f7f1ff', cursorWidth: 2, barWidth: 3, barGap: 2,
      barRadius: 3, normalize: true, autoScroll: true, hideScrollbar: false, plugins: [plugin, timeline] })
    wave.current = ws
    let initial = true
    const update = (r, finalized = true) => { if (!initial && !syncing.current) callback.current({ start: r.start, end: r.end }, finalized) }
    plugin.on('region-created', r => {
      plugin.getRegions().filter(other => other.id !== r.id).forEach(other => other.remove()); update(r, false)
    })
    plugin.on('region-update', r => update(r, false)); plugin.on('region-updated', r => update(r, true))
    ws.on('ready', () => {
      if (wave.current !== ws) return
      setReady(true)
      const current = selection.current
      if (validSelection(current, ws.getDuration())) plugin.addRegion({ ...current, color: 'rgba(176,128,255,.28)', minLength: .001, drag: true, resize: true })
      initial = false
    })
    const stopDrag = plugin.enableDragSelection({ color: 'rgba(176,128,255,.28)', minLength: .001 })
    ws.on('play', () => { setPlaying(true); playCallback.current?.() }); ws.on('pause', () => setPlaying(false))
    ws.on('finish', () => setPlaying(false)); ws.on('timeupdate', setTime)
    ws.on('resize', () => { if (zoomRef.current > 1) ws.zoom(ws.getWidth() / ws.getDuration() * zoomRef.current) })
    ws.on('error', error => {
      if (error.name !== 'AbortError' && wave.current === ws) {
        setReady(false); setFailed(true)
        errors.current('Waveform could not load. Check the backend connection or upload the recording again.')
      }
    })
    return () => { stopDrag(); if (wave.current === ws) wave.current = null; ws.destroy() }
  }, [url])
  useEffect(() => { if (disabled) wave.current?.pause() }, [disabled])
  useEffect(() => { wave.current?.pause() }, [pauseSignal])
  function updateInput(key, value) {
    setDraft(previous => ({ ...previous, [key]: value }))
    callback.current({ ...selection.current, [key]: value === '' ? NaN : Number(value) }, false)
  }
  function changeZoom(next) {
    try {
      wave.current.zoom(next === 1 ? 0 : wave.current.getWidth() / duration * next)
      if (next === 1) wave.current.setScrollTime(0)
      zoomRef.current = next; setZoom(next)
    } catch { errors.current('Zoom is unavailable until the waveform has loaded.') }
  }
  async function playSelection() {
    try { wave.current.pause(); await wave.current.play(region.start, region.end) }
    catch { errors.current('Playback could not start. Try Play selection again.') }
  }
  return <div className="waveform-editor">
    <div className="wave-tools"><span className="wave-caption">Drag to select a phrase</span>
      <div className="zoom-controls" role="group" aria-label="Waveform zoom">
        <button disabled={!ready || disabled || zoom === 1} onClick={() => changeZoom(Math.max(1, zoom / 2))} aria-label="Zoom out">−</button>
        <output aria-live="polite">{zoom}×</output>
        <button disabled={!ready || disabled || zoom >= 16} onClick={() => changeZoom(Math.min(16, zoom * 2))} aria-label="Zoom in">+</button>
        <button disabled={!ready || disabled || zoom === 1} onClick={() => changeZoom(1)}>Reset zoom</button>
      </div>
    </div>
    <div className={`wave ${disabled ? 'locked' : ''}`} ref={container} aria-label="Current recording waveform with timestamp ruler. Drag to select a phrase." />
    {!ready && <p className="muted" role="status">{failed ? 'Waveform unavailable. Check the connection or upload again.' : 'Loading waveform and timestamps…'}</p>}
    <div className="transport">
      <button className="play" disabled={!ready || disabled} onClick={() => wave.current?.playPause()?.catch(() => errors.current('Playback could not start. Try again.'))} aria-label={playing ? 'Pause recording' : 'Play current recording'}><Icon name={playing ? 'pause' : 'play'} size={23}/></button>
      <button className="secondary" disabled={!ready || disabled || !valid} aria-describedby={!valid ? 'selection-help' : undefined} onClick={playSelection}><Icon name="play" size={16}/>Play selection</button>
      <div className="history-toolbar" role="group" aria-label="Edit history controls">
        <button className="icon-button" title="Undo last edit" aria-label="Undo last edit" disabled={disabled || !canUndo} onClick={undo}><Icon name="undo"/><span className="sr-only">Undo last edit</span></button>
        <button className="icon-button" title="Redo last edit" aria-label="Redo last edit" disabled={disabled || !canRedo} onClick={redo}><Icon name="redo"/><span className="sr-only">Redo last edit</span></button>
      </div>
      <span className="time"><span className="playback-label">Current</span> {stamp(time)} <span>/ {stamp(duration)}</span></span>
    </div>
    <div className="selection-fields">{['start', 'end'].map(key => <label key={key} htmlFor={`selection-${key}`}>{key === 'start' ? 'Start' : 'End'}
      <div className="timestamp-input"><input id={`selection-${key}`} aria-label={`Selection ${key} in seconds`} type="number" step="0.001" min="0" max={duration}
        disabled={disabled} value={draft[key]} aria-invalid={!valid} aria-describedby="selection-help"
        onFocus={() => { focused.current = key }} onBlur={() => { callback.current(selection.current, true); focused.current = null; setDraft(previous => ({ ...previous, [key]: inputValue(selection.current[key]) })) }}
        onChange={e => updateInput(key, e.target.value)}/><small>seconds</small></div>
    </label>)}<div className="selection-summary"><span>Selection duration</span><output>{valid ? `${(region.end - region.start).toFixed(3)}s` : emptySelection ? 'No selection' : 'Invalid selection'}</output></div></div>
    <p className={valid ? 'field-help' : 'field-help invalid'} id="selection-help">{valid
      ? `Selected ${stamp(region.start)}–${stamp(region.end)}. Adjust the edges or enter exact times.`
      : emptySelection ? 'Select your next segment by dragging on the updated waveform, or enter Start and End. These timestamps belong to the current edited recording.'
      : 'Enter Start and End within the recording. End must follow Start by at least 0.001 seconds. Your edit text is preserved.'}</p>
    <p className="field-help zoom-hint">{zoom === 1 ? 'Zoom in for a more precise selection.' : 'Scroll to move through the zoomed recording.'}</p>
  </div>
}
