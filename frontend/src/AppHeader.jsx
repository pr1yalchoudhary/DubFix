import Icon from './Icon'

export default function AppHeader({ recordingName, busy, canExport, onNew, onExport }) {
  return <header className="app-header"><div className="header-inner">
    <div className="brand-block"><a className="brand" href="/" aria-label="Tweeq home">Tweeq</a><p>One mistake shouldn't mean another take.</p></div>
    {recordingName && <div className="header-actions"><button className="quiet" disabled={busy} onClick={onNew}>New Recording</button><button className="secondary" disabled={busy || !canExport} onClick={onExport}><Icon name="download"/>Export</button></div>}
  </div></header>
}
