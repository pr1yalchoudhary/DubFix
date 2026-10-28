import io
from email.parser import BytesParser
from email.policy import default
import httpx
import pytest
from app import audio, fish_audio
from app.sessions import sessions
from test_workflow import client, upload


def test_asr_exact_current_region_cache_and_revision(client, monkeypatch):
    real_client = httpx.AsyncClient
    calls = []
    sid = upload(client).json()['session_id']
    session = sessions[sid]
    original = audio.AudioSegment.from_wav(session.folder / 'original.wav')
    edited = original.reverse()
    edited.export(session.folder / 'edited.wav', format='wav')
    session.current = 'edited.wav'; session.revision = 1
    async def handler(request):
        assert str(request.url) == 'https://api.fish.audio/v1/asr'
        assert request.headers['authorization'] == 'Bearer local-asr-fixture'
        assert request.headers['model'] == 'transcribe-1-pro'
        message = BytesParser(policy=default).parsebytes(('Content-Type: ' + request.headers['content-type'] + '\r\n\r\n').encode() + request.content)
        parts = {p.get_param('name', header='content-disposition'): p.get_payload(decode=True) for p in message.iter_parts()}
        sent = audio.AudioSegment.from_wav(io.BytesIO(parts['audio']))
        assert sent.raw_data == edited[1234:4567].raw_data
        assert len(sent) == 3333
        assert parts['diarize'] == b'false' and parts['tag_audio_events'] == b'false'
        calls.append(1)
        return httpx.Response(200, json={'text': '<|speaker:0|> Existing words.'})
    monkeypatch.setenv('FISH_AUDIO_API_KEY', 'local-asr-fixture')
    monkeypatch.setattr(fish_audio.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    body = dict(session_id=sid, revision=1, start=1.234, end=4.567)
    first = client.post('/api/transcribe', json=body).json()
    assert first['text'] == 'Existing words.' and not first['cached']
    assert client.post('/api/transcribe', json=body).json()['cached']
    assert len(calls) == 1
    assert client.post('/api/transcribe', json={**body, 'revision': 0}).status_code == 409
    session.revision = 2
    assert client.post('/api/transcribe', json={**body, 'revision': 2}).status_code == 200
    assert len(calls) == 2


@pytest.mark.parametrize('status,payload', [(403, {}), (200, {'text': ''}), (200, {'wrong': 'field'})])
def test_asr_failure_has_manual_fallback_without_retry(client, monkeypatch, status, payload):
    real_client = httpx.AsyncClient
    calls = []
    async def handler(request):
        calls.append(1)
        return httpx.Response(status, json=payload)
    monkeypatch.setenv('FISH_AUDIO_API_KEY', 'local-asr-fixture')
    monkeypatch.setattr(fish_audio.httpx, 'AsyncClient', lambda **kw: real_client(transport=httpx.MockTransport(handler), **kw))
    sid = upload(client).json()['session_id']
    response = client.post('/api/transcribe', json=dict(session_id=sid, revision=0, start=1, end=4))
    assert response.status_code == 502
    assert 'manually' in response.json()['detail']
    assert not sessions[sid].transcripts and len(calls) == 1
