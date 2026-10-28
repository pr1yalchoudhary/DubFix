export const PRESETS = [
  ['Natural', ''],
  ['Excited', 'warm, conversational enthusiasm with restrained emphasis; keep the reference accent, vocal character and natural pacing; avoid shouting or exaggerated pitch'],
  ['Confident', 'quietly confident and conversational, with clear but gentle emphasis'],
  ['Calm', 'calm, gentle, reassuring tone'],
  ['Nervous', 'slightly hesitant and understated, with small natural pauses'],
  ['Sad', 'sad, subdued, emotionally restrained'],
  ['Sarcastic', 'subtle dry irony with a light conversational touch'],
  ['Whisper', 'speaking softly in a whisper'],
]

export function editScript(text, start, end, kind) {
  start = Math.max(0, Math.min(start, text.length))
  end = Math.max(start, Math.min(end, text.length))
  let insert, cursor
  if (kind === 'emphasis' || kind === 'whisper') {
    if (start === end || !text.slice(start, end).trim()) return { error: 'Select a word or phrase in the text first.' }
    insert = `<${kind}>${text.slice(start, end)}</${kind}>`
    cursor = start + insert.length
  } else {
    const cue = { laugh: '[laughing]', sigh: '[sigh]', breath: '[breath]', pause: '[pause]' }[kind]
    if (!cue) return { error: 'Choose a supported delivery control.' }
    end = start
    insert = `${start && !/\s/.test(text[start - 1]) ? ' ' : ''}${cue}${start < text.length && !/\s/.test(text[start]) ? ' ' : ''}`
    cursor = start + insert.length
  }
  const value = text.slice(0, start) + insert + text.slice(end)
  if (value.length > 1000) return { error: 'Keep the text under 1,000 characters including tags and cues.' }
  return { value, cursor }
}
