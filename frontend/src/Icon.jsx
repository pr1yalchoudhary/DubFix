// Original geometric UI icons; no external font, asset package or proprietary artwork.
const paths = {
  waveform: 'M3 10v4m4-7v10m5-14v18m5-14v10m4-7v4',
  upload: 'M12 16V3m-5 5 5-5 5 5M4 15v5a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-5',
  folder: 'M3 7V5a1 1 0 0 1 1-1h5l2 3h9a1 1 0 0 1 1 1v11a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V7Z',
  undo: 'm8 4-5 5 5 5M3 9h11a6 6 0 0 1 0 12h-3',
  redo: 'm16 4 5 5-5 5m5-5H10a6 6 0 0 0 0 12h3',
  download: 'M12 3v13m-5-5 5 5 5-5M4 17v4h16v-4',
  arrow: 'M4 12h16m-6-6 6 6-6 6',
  check: 'm5 12 4 4L19 6',
  shield: 'M12 3 4 6v6c0 5 8 9 8 9s8-4 8-9V6l-8-3Z',
}

export default function Icon({ name, size = 20, className = '' }) {
  return <svg className={`icon ${className}`} width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" focusable="false">
    {name === 'play' ? <path d="m9 5 11 7-11 7V5Z" fill="currentColor" stroke="none"/> : name === 'pause' ? <path d="M8 5v14M16 5v14" strokeWidth="4"/> : <path d={paths[name] || paths.waveform}/>}
  </svg>
}
