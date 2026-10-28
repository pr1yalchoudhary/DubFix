import test from 'node:test'
import assert from 'node:assert/strict'
import { editScript, PRESETS } from './deliveryText.js'

test('emphasis wraps exactly the selected phrase', () => {
  const result = editScript('Our new product launches.', 4, 15, 'emphasis')
  assert.equal(result.value, 'Our <emphasis>new product</emphasis> launches.')
  assert.equal(result.cursor, result.value.indexOf(' launches.'))
})
test('whisper uses paired tags and requires a selection', () => {
  assert.equal(editScript('Keep a secret.', 0, 13, 'whisper').value, '<whisper>Keep a secret</whisper>.')
  assert.match(editScript('Hello', 2, 2, 'whisper').error, /Select a word/)
})
test('sound cues insert at the cursor and preserve surrounding text', () => {
  assert.equal(editScript('Hello world', 5, 5, 'sigh').value, 'Hello [sigh] world')
  assert.equal(editScript('Hello', 0, 5, 'laugh').value, '[laughing] Hello')
  assert.equal(editScript('Hello ', 6, 6, 'breath').value, 'Hello [breath]')
  assert.equal(editScript('Hello', 5, 5, 'pause').value, 'Hello [pause]')
})
test('markup helpers enforce the script length limit', () => {
  assert.match(editScript('x'.repeat(1000), 0, 10, 'emphasis').error, /1,000/)
})
test('Natural is empty and all eight presets are available', () => {
  assert.equal(PRESETS.length, 8)
  assert.equal(PRESETS[0][1], '')
})
