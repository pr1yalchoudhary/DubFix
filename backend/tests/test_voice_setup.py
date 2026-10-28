import httpx
import msgpack
import pytest

from app import fish_audio
from app.sessions import sessions
from test_workflow import client, upload, wav_bytes


def wire(monkeypatch, handler):
    actual = httpx.AsyncClient
    monkeypatch.setenv('FISH_AUDIO_API_KEY', 'voice-setup-fixture-only')
    monkeypatch.setattr(fish_audio.httpx, 'AsyncClient', lambda **kw: actual(transport=httpx.MockTransport(handler), **kw))


def payload(sid, **extra):
    return dict(session_id=sid, start=1, end=2, replacement_text='Friday', **extra)


def test_automatic_voice_setup_omits_texts_caches_model_and_preserves_pipeline(client, monkeypatch):
    calls = []
    models = []
    async def handler(request):
        calls.append((request.method, request.url.path))
        assert request.headers['authorization'] == 'Bearer voice-setup-fixture-only'
        if request.url.path == '/model':
            assert request.method == 'POST'
            assert 'multipart/form-data' in request.headers['content-type']
            assert b'name="texts"' not in request.content
            assert b'name="voices"' in request.content and b'RIFF' in request.content
            assert (sessions[sid].folder / 'reference.wav').read_bytes() in request.content
            assert b'private' in request.content and b'fast' in request.content
            return httpx.Response(201, json={'_id': 'cached-voice', 'state': 'created'})
        if request.url.path == '/model/cached-voice':
            return httpx.Response(200, json={'_id': 'cached-voice', 'state': 'trained'})
        assert request.url.path == '/v1/tts'
        models.append(request.headers['model'])
        body = msgpack.unpackb(request.content, raw=False)
        assert body['reference_id'] == 'cached-voice'
        assert 'references' not in body
        assert body['format'] == 'wav' and body['sample_rate'] == 44100
        return httpx.Response(200, content=wav_bytes(2, 660))
    wire(monkeypatch, handler)
    sid = upload(client).json()['session_id']
    assert not calls  # Upload remains local and incurs no automatic provider work.
    original = client.get(f'/api/audio/{sid}?version=original').content
    first = client.post('/api/preview', json=payload(sid))
    assert first.status_code == 200, first.text
    second = client.post('/api/preview', json=payload(sid, mode='delivery', segment_text='Hello', direction='calm'))
    assert second.status_code == 200, second.text
    assert calls.count(('POST', '/model')) == 1
    assert models == [fish_audio.correction_model(), 'drama-3']
    assert calls.count(('POST', '/v1/tts')) == 2
    assert sessions[sid].voice_model_id == 'cached-voice'
    preview = first.json()
    assert client.get(preview['preview_url']).content[:4] == b'RIFF'
    assert (sessions[sid].folder / (preview['preview_id'] + '-provider.wav')).read_bytes() == wav_bytes(2, 660)
    result = client.post('/api/replace', json=dict(session_id=sid, start=1, end=2, preview_id=preview['preview_id']))
    assert result.status_code == 200
    assert client.get(f'/api/audio/{sid}?version=original').content == original
    assert client.get(result.json()['waveform_url']).content != original
    assert client.get(f'/api/export/{sid}').headers['content-disposition'].endswith('"tweeq-corrected.mp3"')
    assert calls.count(('POST', '/v1/tts')) == 2


@pytest.mark.parametrize('state', ['training', 'failed'])
def test_processing_or_failed_voice_is_cached_not_recreated(client, monkeypatch, state):
    calls = []
    async def handler(request):
        calls.append(request.url.path)
        assert request.url.path != '/v1/tts'
        return httpx.Response(201 if request.url.path == '/model' else 200, json={'_id': 'pending-voice', 'state': state})
    wire(monkeypatch, handler)
    sid = upload(client).json()['session_id']
    for _ in range(2):
        response = client.post('/api/preview', json=payload(sid))
        assert response.status_code in (502, 503)
    assert calls.count('/model') == 1


def test_voice_creation_is_not_retried_on_timeout(client, monkeypatch):
    calls = []
    async def handler(request):
        calls.append(request.url.path)
        raise httpx.ReadTimeout('private details must not escape')
    wire(monkeypatch, handler)
    sid = upload(client).json()['session_id']
    response = client.post('/api/preview', json=payload(sid))
    assert response.status_code == 502
    assert response.json()['error_code'] == 'fish_voice_connection'
    assert 'private details' not in response.text
    assert calls == ['/model']


def test_no_reference_transcript_and_no_credentials_reports_configuration(client, monkeypatch):
    monkeypatch.delenv('FISH_AUDIO_API_KEY', raising=False)
    sid = upload(client).json()['session_id']
    response = client.post('/api/preview', json=payload(sid))
    assert response.status_code == 503
    assert 'configuration' in response.json()['detail']
