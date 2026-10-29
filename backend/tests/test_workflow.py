"""Local audio tests use explicit fixtures, never substitutes for live AI validation."""
import io
import wave
from uuid import uuid4

import httpx
import msgpack
import pytest
from fastapi.testclient import TestClient
from pydub import AudioSegment
from pydub.generators import Sine

from app import audio, fish_audio, main
from app.sessions import previews, sessions


def wav_bytes(seconds=16, frequency=220):
    out = io.BytesIO()
    Sine(frequency).to_audio_segment(duration=seconds * 1000).apply_gain(-15).export(out, format='wav')
    return out.getvalue()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv('DEMO_ACCESS_TOKEN', 'local-test-access-token-not-for-deployment')
    monkeypatch.setattr(main, 'DATA', tmp_path)
    sessions.clear(); previews.clear()
    with TestClient(main.app, headers={'Authorization': 'Bearer local-test-access-token-not-for-deployment'}) as client:
        yield client
    sessions.clear(); previews.clear()


def upload(client, data=None, consent='true', filename='recording.wav'):
    return client.post('/api/upload', files={'file': (filename, data if data is not None else wav_bytes(), 'audio/wav')}, data={'consent': consent})


def test_consent_and_bad_uploads(client):
    assert upload(client, consent='false').status_code == 400
    assert upload(client, filename='voice.exe').status_code == 400
    assert upload(client, data=b'').status_code == 400
    assert upload(client, data=b'not audio').status_code == 400
    assert upload(client, data=b'x' * (25 * 1024 * 1024 + 1)).status_code == 413
    assert client.get('/api/audio/not-a-uuid').status_code == 422
    assert client.get('/api/audio/' + str(uuid4())).status_code == 404


def test_short_and_silent_reference_remain_playable(client):
    result = upload(client, wav_bytes(4)).json()
    assert result['voice_status'] == 'unavailable'
    assert client.get(result['waveform_url']).status_code == 200
    out = io.BytesIO()
    AudioSegment.silent(duration=12000).export(out, format='wav')
    assert upload(client, out.getvalue()).json()['voice_status'] == 'unavailable'


def test_upload_reference_and_missing_key(client, monkeypatch):
    monkeypatch.delenv('FISH_AUDIO_API_KEY', raising=False)
    result = upload(client).json()
    assert result['duration'] == 16
    assert result['reference'] == {'start': 5, 'end': 15}
    assert result['voice_status'] == 'configuration_required'
    body = dict(session_id=result['session_id'], start=2, end=3, replacement_text='April fifth', reference_text='Reference words')
    assert client.post('/api/preview', json=body).status_code == 503
    body['end'] = 200
    assert client.post('/api/preview', json=body).status_code == 400
    body['end'] = 3; body['replacement_text'] = ' '
    assert client.post('/api/preview', json=body).status_code == 422


def test_correction_preview_ownership_staleness_and_mp3(client, monkeypatch):
    calls = []
    async def fixture_generation(*args):
        calls.append(args)
        return wav_bytes(2, 440)
    monkeypatch.setattr(fish_audio, 'generate', fixture_generation)
    session = upload(client).json()
    sid = session['session_id']
    original = client.get(f'/api/audio/{sid}?version=original').content
    body = dict(session_id=sid, start=4, end=5, replacement_text='April fifth', reference_text='Reference words')
    preview = client.post('/api/preview', json=body).json()
    assert len(preview['continuity_warnings']) == 2
    assert preview['duration_change'] == 1
    clip = client.get(preview['preview_url']).content
    assert AudioSegment.from_wav(io.BytesIO(clip)).duration_seconds == 2
    replacement = dict(session_id=sid, start=4, end=5, preview_id=preview['preview_id'])
    wrong = {**replacement, 'end': 6}
    assert client.post('/api/replace', json=wrong).status_code == 409
    other = upload(client).json()['session_id']
    assert client.post('/api/replace', json={**replacement, 'session_id': other}).status_code == 400
    corrected = client.post('/api/replace', json=replacement)
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()['duration'] == 17
    assert len(calls) == 1  # replacement must never generate speech again
    assert client.get(f'/api/audio/{sid}?version=original').content == original
    current = AudioSegment.from_wav(io.BytesIO(client.get(corrected.json()['waveform_url']).content))
    preview_audio = AudioSegment.from_wav(io.BytesIO(clip))
    assert current[4100:5700].raw_data == preview_audio[100:1700].raw_data
    assert client.post('/api/replace', json=replacement).status_code == 409
    exported = client.get(f'/api/export/{sid}')
    assert exported.status_code == 200
    path = sessions[sid].folder / 'download.mp3'; path.write_bytes(exported.content)
    duration, stream = audio.probe(path)
    assert 16.8 < duration < 17.1
    assert stream['codec_name'] == 'mp3'
    assert int(stream['bit_rate']) == 192000


@pytest.mark.parametrize('start,end', [(0, 1), (15, 16), (0, 16), (.01, .03)])
def test_splice_boundaries(tmp_path, start, end):
    source, clip, target = [tmp_path / name for name in ('source.wav', 'clip.wav', 'target.wav')]
    source.write_bytes(wav_bytes()); clip.write_bytes(wav_bytes(1))
    audio.splice(source, clip, start, end, target)
    with wave.open(str(target)) as result:
        assert result.getnframes() > 0 and result.getframerate() == 44100


def test_empty_generation_not_saved(client, monkeypatch):
    async def invalid(*args): return b'broken'
    monkeypatch.setattr(fish_audio, 'generate', invalid)
    sid = upload(client).json()['session_id']
    result = client.post('/api/preview', json=dict(session_id=sid, start=1, end=2, replacement_text='hello', reference_text='reference'))
    assert result.status_code == 400
    assert not previews


def test_ninety_second_mp3_upload(client, tmp_path):
    source, mp3 = tmp_path / 'source.wav', tmp_path / 'source.mp3'
    source.write_bytes(wav_bytes(90))
    audio.export_mp3(source, mp3)
    response = upload(client, mp3.read_bytes(), filename='ninety-seconds.mp3')
    assert response.status_code == 200
    result = response.json()
    assert 89.9 < result['duration'] < 90.1
    assert result['reference'] == {'start': 5, 'end': 15}
    assert client.get(result['waveform_url']).content[:4] == b'RIFF'


@pytest.mark.parametrize('status', [401, 402, 403, 422, 429, 503])
def test_fish_errors_and_retry(client, monkeypatch, status):
    monkeypatch.setenv('FISH_AUDIO_API_KEY', 'test-secret-never-returned')
    count = []
    actual_client = httpx.AsyncClient
    async def handler(request):
        count.append(request)
        payload = msgpack.unpackb(request.content, raw=False)
        assert payload['references'][0]['audio'][:4] == b'RIFF'
        assert payload['references'][0]['text'] == 'exact reference'
        assert request.headers['content-type'] == 'application/msgpack'
        return httpx.Response(status, json={'message': 'test-secret-never-returned'})
    monkeypatch.setattr(fish_audio.httpx, 'AsyncClient', lambda **kw: actual_client(transport=httpx.MockTransport(handler), **kw))
    sid = upload(client).json()['session_id']
    response = client.post('/api/preview', json=dict(session_id=sid, start=1, end=2, replacement_text='hello', reference_text='exact reference'))
    assert response.status_code in (502, 429)
    assert 'test-secret-never-returned' not in response.text
    assert response.json()['error_code'] == f'fish_http_{status}'
    assert response.json()['upstream_status'] == status
    assert len(count) == (2 if status in (429, 503) else 1)
