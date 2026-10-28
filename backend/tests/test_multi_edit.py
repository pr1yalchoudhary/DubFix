import io
import httpx
import msgpack

from app import audio, fish_audio
from app.sessions import sessions
from test_workflow import client, upload, wav_bytes


def frequency(clip):
    values = clip.get_array_of_samples()
    crossings = sum(a <= 0 < b for a, b in zip(values, values[1:]))
    return crossings / clip.duration_seconds


def test_two_independent_modes_current_timestamps_export_and_undo(client, monkeypatch, tmp_path):
    real_client = httpx.AsyncClient
    calls = []
    async def handler(request):
        if request.url.path == '/model':
            return httpx.Response(201, json={'_id': 'shared-voice', 'state': 'trained'})
        if request.url.path == '/v1/asr':
            assert request.headers['model'] == 'transcribe-1-pro'
            return httpx.Response(200, json={'text': "I can't wait for you to try it!"})
        body = msgpack.unpackb(request.content, raw=False)
        calls.append((request.headers['model'], body['text']))
        return httpx.Response(200, content=wav_bytes(4 if len(calls) == 1 else 3, 660 if len(calls) == 1 else 880))
    monkeypatch.setenv('FISH_AUDIO_API_KEY', 'local-multi-edit-fixture')
    monkeypatch.setattr(fish_audio.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    sid = upload(client).json()['session_id']
    original = client.get(f'/api/audio/{sid}?version=original').content
    first = client.post('/api/preview', json=dict(session_id=sid, revision=0, start=1, end=4,
        original_text="We're launching next Monday", replacement_text="We're launching next Friday.")).json()
    # A delivery Apply cannot reuse a Correct Speech preview, even on the same region.
    wrong = client.post('/api/replace', json=dict(session_id=sid, revision=0, start=1, end=4, preview_id=first['preview_id'], mode='delivery'))
    assert wrong.status_code == 409
    applied1 = client.post('/api/replace', json=dict(session_id=sid, revision=0, start=1, end=4, preview_id=first['preview_id'], mode='correct'))
    assert applied1.status_code == 200
    one = applied1.json()
    assert one['duration'] == 17 and one['edit_count'] == 1
    first_audio = client.get(one['waveform_url']).content
    stale = client.post('/api/preview', json=dict(session_id=sid, revision=0, start=1, end=4, replacement_text='stale'))
    assert stale.status_code == 409 and len(calls) == 1
    detected = client.post('/api/transcribe', json=dict(session_id=sid, revision=1, start=6, end=10)).json()
    assert detected['text'] == "I can't wait for you to try it!"
    assert client.post('/api/transcribe', json=dict(session_id=sid, revision=1, start=6, end=10)).json()['cached']
    # The second interval uses the UPDATED timeline (+1.0 s), not original timestamps.
    second = client.post('/api/preview', json=dict(session_id=sid, revision=1, start=6, end=10,
        mode='delivery', replacement_text="I can't wait for you to try it!", segment_text=detected['text'], direction='excited and dramatic')).json()
    applied2 = client.post('/api/replace', json=dict(session_id=sid, revision=1, start=6, end=10, preview_id=second['preview_id'], mode='delivery'))
    assert applied2.status_code == 200
    two = applied2.json()
    assert two['duration'] == 16 and two['edit_count'] == 2
    assert [e['mode'] for e in two['edit_history']] == ['correct', 'delivery']
    assert all(e['status'] == 'applied' for e in two['edit_history'])
    assert two['edit_history'][0]['original_text'] == "We're launching next Monday"
    assert two['edit_history'][0]['replacement_text'] == "We're launching next Friday."
    assert two['edit_history'][1]['direction'] == 'excited and dramatic'
    assert calls[0][1] == "We're launching next Friday."
    assert calls[1] == ('drama-3', "[excited and dramatic]\nI can't wait for you to try it!")
    current = client.get(two['waveform_url']).content
    first_wav, final_wav = audio.AudioSegment.from_wav(io.BytesIO(first_audio)), audio.AudioSegment.from_wav(io.BytesIO(current))
    assert final_wav[1500:3500].raw_data == first_wav[1500:3500].raw_data
    assert abs(frequency(final_wav[6200:8200]) - 880) < 2
    assert client.get(f'/api/audio/{sid}?version=original').content == original
    exported = client.get(f'/api/export/{sid}')
    mp3 = tmp_path / 'both-edits.mp3'; mp3.write_bytes(exported.content)
    decoded = audio.convert(mp3, tmp_path / 'decoded.wav')
    assert abs(frequency(decoded[1500:3500]) - 660) < 3
    assert abs(frequency(decoded[6200:8200]) - 880) < 3
    undo = client.post(f'/api/undo/{sid}', json={'revision': 2})
    assert undo.status_code == 200
    restored = undo.json()
    assert restored['revision'] == 3 and restored['edit_count'] == 1 and restored['duration'] == 17
    assert client.get(restored['waveform_url']).content == first_audio
    assert restored['edit_history'][1]['status'] == 'undone'
    # Pre-undo and wrong-version previews must stay invalid, even if time ranges happen to match.
    assert client.post('/api/replace', json=dict(session_id=sid, revision=1, start=6, end=10, preview_id=second['preview_id'], mode='delivery')).status_code == 409
    assert client.post(f'/api/undo/{sid}', json={'revision': 2}).status_code == 409
    assert client.post(f'/api/undo/{sid}', json={'revision': 3}).json()['edit_count'] == 0
    assert client.get(f'/api/audio/{sid}').content == original
    redo = client.post(f'/api/redo/{sid}', json={'revision': 4}).json()
    assert redo['edit_count'] == 1 and client.get(redo['waveform_url']).content == first_audio
    redo = client.post(f'/api/redo/{sid}', json={'revision': 5}).json()
    assert redo['edit_count'] == 2 and client.get(redo['waveform_url']).content == current
    assert len(calls) == 2  # Apply, Undo, Compare and Export never synthesize speech.
