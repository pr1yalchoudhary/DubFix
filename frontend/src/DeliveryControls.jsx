import { useRef, useState } from 'react'
import { editScript, PRESETS } from './deliveryText'

export const EMPTY_DELIVERY = { direction: '', segment_text: '', language: 'original', translated_text: '' }

export default function DeliveryControls({ value, onChange, disabled, detecting }) {
  const segment = useRef(null), translated = useRef(null)
  const [hint, setHint] = useState('')
  const translating = value.language !== 'original'
  const target = translating ? translated : segment
  const field = translating ? 'translated_text' : 'segment_text'
  function update(key, next) {
    setHint('')
    onChange({ ...value, [key]: next, ...(key === 'language' ? { translated_text: '' } : {}) })
  }
  function apply(kind) {
    const input = target.current
    if (!input) return
    const result = editScript(value[field], input.selectionStart, input.selectionEnd, kind)
    if (result.error) { setHint(result.error); return }
    update(field, result.value)
    requestAnimationFrame(() => { input.focus(); input.setSelectionRange(result.cursor, result.cursor) })
  }
  const tones = ['Natural', 'Excited', 'Calm', 'Confident', 'Sad', 'Nervous', 'Whisper'].map(label => PRESETS.find(item => item[0] === label))
  tones.push(['Dramatic', 'dramatic but restrained, with natural pacing and subtle emphasis'])
  return <div className="delivery-controls">
    <label className="field-label" htmlFor="segment-text">Your words</label>
    <textarea ref={segment} id="segment-text" rows="3" maxLength={1000} value={value.segment_text} disabled={disabled || detecting} placeholder="Detected speech appears here. You can correct it if needed." onChange={e => update('segment_text', e.target.value)}/>
    <fieldset disabled={disabled} className="preset-group"><legend className="field-label">How should it sound?</legend><div className="presets">
      {tones.map(([label, direction]) => <button key={label} type="button" aria-pressed={value.direction === direction} className={value.direction === direction ? 'chosen' : ''} onClick={() => update('direction', direction)}>{label}</button>)}
    </div></fieldset>
    <label className="field-label" htmlFor="delivery-direction">Custom direction <span className="optional">optional</span></label>
    <textarea id="delivery-direction" rows="2" maxLength={400} placeholder="Describe the delivery in your own words…" value={value.direction} disabled={disabled} onChange={e => update('direction', e.target.value)}/>
    <details className="more-options"><summary>More options</summary>
      <label className="field-label" htmlFor="delivery-language">Language</label>
      <select id="delivery-language" value={value.language} disabled={disabled} onChange={e => update('language', e.target.value)}>
        <option value="original">Original language</option><option value="en">English</option><option value="hi">Hindi</option><option value="es">Spanish</option><option value="fr">French</option>
      </select>
      {translating && <><label className="field-label" htmlFor="translated-text">Text in your selected language <span aria-hidden="true">*</span></label>
        <textarea ref={translated} id="translated-text" rows="3" maxLength={1000} required value={value.translated_text} disabled={disabled} placeholder="Enter your manually translated words…" onChange={e => update('translated_text', e.target.value)}/>
        <p className="field-help">Enter the translated text manually. Voice similarity and pronunciation may vary across languages.</p>
      </>}
      <p className="field-label">Word effects and sound cues</p>
      <div className="delivery-toolbar" role="group" aria-label={`Delivery controls for ${translating ? 'translated' : 'segment'} text`}>
        {[['emphasis', 'Emphasis'], ['whisper', 'Whisper selected words'], ['laugh', 'Laugh'], ['sigh', 'Sigh'], ['breath', 'Breath'], ['pause', 'Pause']].map(([kind, label]) =>
          <button key={kind} type="button" disabled={disabled} onMouseDown={e => e.preventDefault()} onClick={() => apply(kind)}>{label}</button>)}
      </div>
      <p className="field-help">{translating ? 'Effects apply to the translated text. ' : ''}Select words for Emphasis or Whisper. Sound cues insert at the cursor.</p>
      {PRESETS.filter(([label]) => !tones.some(([name]) => name === label)).map(([label, direction]) => <button key={label} className="secondary" disabled={disabled} aria-pressed={value.direction === direction} onClick={() => update('direction', direction)}>{label}</button>)}
      <p className="field-help">Natural leaves the direction empty. Stronger directions may change pitch and pacing.</p>
    </details>
    {hint && <p className="toolbar-hint" role="status">{hint}</p>}
    <small className="character-count">{value[field].length}/1,000</small>
  </div>
}
