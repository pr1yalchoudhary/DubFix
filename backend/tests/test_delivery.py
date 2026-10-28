"""Contract tests use explicit fixture audio; acoustic Drama 3 tests need real credentials."""
import httpx
import msgpack
import pytest

from app import delivery, fish_audio
from app.sessions import previews, sessions
from test_workflow import client, upload, wav_bytes


@pytest.mark.parametrize('direction,expected', [
    (None, 'Hello everyone!'), ('', 'Hello everyone!'),
    ('excited', '[excited]\nHello everyone!'),
    ('[excited]', '[excited]\nHello everyone!'),
    ('[[excited]]', '[excited]\nHello everyone!'),
])
def test_compose_directions(direction, expected):
    script, _ = delivery.compose('Hello everyone!', direction)
    assert script == expected


def test_preserve_cues_tags_and_avoid_duplicate_direction():
    text = '[excited] Our <emphasis>biggest launch</emphasis>! [sigh] <whisper>Tomorrow.</whisper>'
    assert delivery.compose(text, '[excited]')[0] == text
    for tag in delivery.TAGS:
        script = f'<{tag}>Hello</{tag}> [breath] [pause] [laughing]'
        assert delivery.compose(script)[0] == script


@pytest.mark.parametrize('text', [
    '', '   ', '[sigh]', '<emphasis></emphasis>', '<emphasis>Hello',
    '<emphasis>Hello</whisper>', '<emphasis><whisper>Hi</emphasis></whisper>',
    '<script>alert(1)</script>', '<emphasis class="x">Hi</emphasis>',
    'Hello <', 'Hello >', 'Hi [sigh', 'Hi sigh]', 'Hi [[sigh]]', 'Hi []',
])
def test_invalid_script(text):
    with pytest.raises(ValueError):
        delivery.compose(text)


def test_manual_translation():
    script, _ = delivery.compose('Hello', 'calm', 'es', 'Hola. [sigh] <whisper>Hasta mañana.</whisper>')
    assert script == '[calm]\nHola. [sigh] <whisper>Hasta mañana.</whisper>'
    assert delivery.compose('नमस्ते दुनिया', language='original')[0] == 'नमस्ते दुनिया'
    with pytest.raises(ValueError, match='Enter the text in your selected language.'):
        delivery.compose('Hello', language='es')
    with pytest.raises(ValueError):
        delivery.compose('Hi', language='made-up')
    with pytest.raises(ValueError):
        delivery.compose('Hi', direction='[excited] Spoken words')


def body(sid, **changes):
    return dict(session_id=sid, start=2, end=3, replacement_text='Welcome!', reference_text='exact reference',
                mode='delivery', segment_text='Welcome!', direction='[excited]', **changes)


def transport(monkeypatch, handler):
    actual_client = httpx.AsyncClient
    monkeypatch.setenv('FISH_AUDIO_API_KEY', 'fixture-key-only')
    monkeypatch.setattr(fish_audio.httpx, 'AsyncClient', lambda **kw: actual_client(transport=httpx.MockTransport(handler), **kw))


def test_wire_model_preview_metadata_selected_take_and_export(client, monkeypatch):
    calls = []
    async def handler(request):
        payload = msgpack.unpackb(request.content, raw=False)
        calls.append((request.headers['model'], payload))
        assert request.headers['content-type'] == 'application/msgpack'
        assert request.headers['authorization'] == 'Bearer fixture-key-only'
        assert 'model' not in payload
        assert payload['references'][0]['audio'][:4] == b'RIFF'
        assert payload['references'][0]['text'] == 'exact reference'
        assert payload['format'] == 'wav'
        return httpx.Response(200, content=wav_bytes(2, 220 * len(calls)))
    transport(monkeypatch, handler)
    monkeypatch.setenv('FISH_AUDIO_MODEL', 's2-pro')
    sid = upload(client).json()['session_id']
    original = client.get(f'/api/audio/{sid}?version=original').content
    first = client.post('/api/preview', json=body(sid))
    assert first.status_code == 200, first.text
    first = first.json()
    second_body = {**body(sid), 'direction': 'calm', 'language': 'es', 'translated_text': 'Hola. [sigh] <whisper>Bienvenidos.</whisper>'}
    second = client.post('/api/preview', json=second_body).json()
    assert first['preview_id'] != second['preview_id']
    assert calls[0][0] == calls[1][0] == 'drama-3'
    assert calls[0][1]['text'] == '[excited]\nWelcome!'
    assert calls[1][1]['text'] == '[calm]\nHola. [sigh] <whisper>Bienvenidos.</whisper>'
    assert calls[1][1]['language'] == 'es'
    item = previews[first['preview_id']]
    assert item.mode == 'delivery' and item.model_used == 'drama-3'
    assert item.direction == 'excited' and item.segment_text == 'Welcome!'
    assert item.created_at and item.path.exists()
    assert client.get(first['preview_url']).content[:4] == b'RIFF'
    assert client.get(f'/api/audio/{sid}').content == original  # multiple previews do not edit recording
    replaced = client.post('/api/replace', json=dict(session_id=sid, preview_id=first['preview_id'], start=2, end=3))
    assert replaced.status_code == 200
    assert len(calls) == 2 and item.used and not previews[second['preview_id']].used
    assert client.get(f'/api/audio/{sid}?version=original').content == original
    assert client.get(f'/api/export/{sid}').status_code == 200
    # Old requests omit mode and still use the configured correction model and plain text.
    old = dict(session_id=sid, start=2, end=3, replacement_text='April fifth', reference_text='exact reference', direction='ignored')
    correct = client.post('/api/preview', json=old)
    assert correct.status_code == 200
    assert correct.json()['mode'] == 'correct'
    assert calls[-1][0] == 's2-pro' and calls[-1][1]['text'] == 'April fifth'
    assert 'language' not in calls[-1][1]


@pytest.mark.parametrize('changes,message', [
    ({'segment_text': ''}, 'Enter the words you want to regenerate.'),
    ({'segment_text': '<whisper>Hi'}, 'Please check the delivery tags in your text.'),
    ({'language': 'es'}, 'Enter the text in your selected language.'),
])
def test_delivery_validation_before_provider(client, monkeypatch, changes, message):
    async def no_request(*args, **kwargs):
        pytest.fail('Invalid delivery scripts must not consume API credits')
    monkeypatch.setattr(fish_audio, 'generate', no_request)
    sid = upload(client).json()['session_id']
    response = client.post('/api/preview', json={**body(sid), **changes})
    assert response.status_code == 400 and response.json()['detail'] == message


def test_drama_unavailable_never_falls_back(client, monkeypatch):
    calls = []
    async def handler(request):
        calls.append(request.headers['model'])
        return httpx.Response(503, json={'message': 'fixture-key-only'})
    transport(monkeypatch, handler)
    sid = upload(client).json()['session_id']
    response = client.post('/api/preview', json=body(sid))
    assert response.status_code == 502
    assert 'Drama 3 is currently unavailable' in response.json()['detail']
    assert 'fixture-key-only' not in response.text
    assert calls == ['drama-3', 'drama-3']
    assert sessions[sid].revision == 0 and not previews


def test_drama_timeout_no_ambiguous_retry(client, monkeypatch):
    calls = []
    async def handler(request):
        calls.append(request.headers['model'])
        raise httpx.ReadTimeout('private upstream details')
    transport(monkeypatch, handler)
    sid = upload(client).json()['session_id']
    response = client.post('/api/preview', json=body(sid))
    assert response.status_code == 504
    assert response.json()['detail'] == 'Performance generation is taking longer than expected. Please try again.'
    assert calls == ['drama-3']


def test_friday_full_preview_to_apply_with_local_wav(client, monkeypatch):
    """Exercise the production adapter and real local splicing, with no provider network."""
    calls = []
    async def handler(request):
        payload = msgpack.unpackb(request.content, raw=False)
        calls.append(payload)
        assert payload['text'] == 'Friday'
        return httpx.Response(200, content=wav_bytes(2, 660))
    transport(monkeypatch, handler)
    sid = upload(client).json()['session_id']
    original = client.get(f'/api/audio/{sid}?version=original').content
    response = client.post('/api/preview', json=dict(session_id=sid, start=2, end=3, replacement_text='Friday', reference_text='exact reference'))
    assert response.status_code == 200
    preview = response.json()
    assert preview['preview_id'] and preview['preview_url'] and preview['duration'] > 0
    assert client.get(preview['preview_url']).content[:4] == b'RIFF'
    assert client.get(f'/api/audio/{sid}?version=current').content == original
    updated = client.post('/api/replace', json=dict(session_id=sid, preview_id=preview['preview_id'], start=2, end=3))
    assert updated.status_code == 200 and updated.json()['revision'] == 1
    assert client.get(updated.json()['waveform_url']).content != original
    assert client.get(f'/api/audio/{sid}?version=original').content == original
    assert client.get(f'/api/export/{sid}').status_code == 200
    assert len(calls) == 1
