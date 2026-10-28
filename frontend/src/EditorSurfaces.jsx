import { stamp } from './WaveformEditor'

// Original, presentation-only components. Editing state stays in App/EditorWorkspace.
export function RecordingSurface({ children }) {
  return <section className="panel workflow-card min-w-0" id="step-select">{children}</section>
}

export function EditingFields({ children, hidden }) {
  return <section hidden={hidden} className="panel workflow-card edit-step min-w-0" id="step-edit">{children}</section>
}

export function ReplacementPreview({ children, hidden }) {
  return <div hidden={hidden} className="replacement-surface" aria-label="Replacement preview">
    {children}
  </div>
}

export function ComparisonExport({ children, hidden }) {
  return <section hidden={hidden} className="panel workflow-card min-w-0" id="step-compare">{children}</section>
}

export function EditHistoryList({ children }) {
  return <details className="history-disclosure" aria-label="Edit History"><summary>Edit History</summary>{children}</details>
}

export function EditingModeControl({ mode, disabled, onChange }) {
  return <div className="mode-switch segmented w-full" role="tablist" aria-label="Editing mode">
    <button id="correct-tab" role="tab" aria-selected={mode === 'correct'} aria-controls="correction-fields" disabled={disabled} className={mode === 'correct' ? 'selected' : ''} onClick={() => onChange('correct')}><span>Correct Speech</span><small>Change what was said</small></button>
    <button id="delivery-tab" role="tab" aria-selected={mode === 'delivery'} aria-controls="correction-fields" disabled={disabled} className={mode === 'delivery' ? 'selected' : ''} onClick={() => onChange('delivery')}><span>Change Delivery</span><small>Change how it was said</small></button>
  </div>
}

export function QualityDisclosure({ report }) {
  if (!(report?.warnings || []).length) return null
  return <details className="quality-notice" open={report.status === 'poor'}><summary>Original recording quality: {report.status === 'poor' ? 'a clearer recording is recommended' : 'review suggested'}</summary>
    <p>Local checks flag signal patterns; they cannot verify intelligibility, speaker identity or overlapping voices.</p>
    <ul>{report.warnings.map((warning, i) => <li key={i}><strong>{warning.message}</strong> {warning.recommendation}
      {(warning.intervals || []).length > 0 && <span> Original times: {warning.intervals.map(interval => `${stamp(interval.start)}–${stamp(interval.end)}`).join(', ')}{warning.more_intervals ? ' (additional intervals omitted)' : ''}.</span>}</li>)}</ul>
  </details>
}
