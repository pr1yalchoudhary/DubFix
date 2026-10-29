"""No provider network. Execute the production Lua in a Redis emulator with Lua."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import AsyncMock

import fakeredis
import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request
from app import fish_audio, main, public_usage as usage
from app.sessions import sessions, previews
from test_workflow import wav_bytes, upload


@pytest.fixture
def store(monkeypatch):
    redis = fakeredis.FakeRedis(decode_responses=True)
    redis.hset(usage.PREFIX + 'budget', mapping={'schema': '1', 'enabled': '1', 'used': '0'})
    monkeypatch.setenv('AI_ACCESS_MODE', 'public')
    monkeypatch.setenv('PUBLIC_GENERATIONS_ENABLED', 'true')
    monkeypatch.setenv('PUBLIC_IP_HASH_SECRET', 'test-network-hash-secret-at-least-32-characters')
    monkeypatch.setenv('PUBLIC_IP_SOURCE', 'peer')
    monkeypatch.delenv('RENDER', raising=False)
    monkeypatch.setenv('FISH_AUDIO_API_KEY', 'mock-provider-key')
    async def command(*args):
        return redis.execute_command(*args)
    monkeypatch.setattr(usage, 'command', command)
    return redis


def run(action, token, ip):
    return asyncio.run(usage.evaluate(action, token, ip))


def visitor(ip):
    import secrets
    token = secrets.token_urlsafe(32)
    run('create', token, ip)
    return token


def test_atomic_global_cap_and_persistence(store, monkeypatch):
    tokens = [(visitor(str(i)), str(i)) for i in range(25)]
    def reserve(pair):
        try:
            run('reserve', *pair)
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False
    with ThreadPoolExecutor(max_workers=16) as pool:
        assert sum(pool.map(reserve, tokens)) == 10
    assert store.hget(usage.PREFIX + 'budget', 'used') == '10'
    assert store.ttl(usage.PREFIX + 'budget') == -1
    # A new client/process against the SAME datastore sees the exhausted budget.
    second_client = fakeredis.FakeRedis(connection_pool=store.connection_pool, decode_responses=True)
    async def command(*args):
        return second_client.execute_command(*args)
    monkeypatch.setattr(usage, 'command', command)
    with pytest.raises(HTTPException) as error:
        run('reserve', *tokens[0])
    assert error.value.status_code == 429


def test_visitor_and_ip_caps_cannot_be_reset_by_new_session(store):
    token = visitor('network')
    assert run('reserve', token, 'network')['remaining'] == 1
    assert run('reserve', token, 'network')['remaining'] == 0
    with pytest.raises(HTTPException) as error:
        run('reserve', token, 'network')
    assert error.value.status_code == 429
    with pytest.raises(HTTPException):
        visitor('network')
    with pytest.raises(HTTPException):
        run('reserve', token, 'other-network')
    assert store.hget(usage.PREFIX + 'budget', 'used') == '2'


def test_concurrent_same_visitor_cannot_exceed_two(store):
    token = visitor('network')
    def reserve(_):
        try:
            run('reserve', token, 'network')
            return True
        except HTTPException as exc:
            assert exc.status_code == 429
            return False
    with ThreadPoolExecutor(max_workers=12) as pool:
        assert sum(pool.map(reserve, range(25))) == 2
    assert store.hget(usage.PREFIX + 'budget', 'used') == '2'


def test_provider_adapter_without_access_context_is_blocked(store, monkeypatch):
    provider = AsyncMock(side_effect=AssertionError('Must not call provider'))
    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)
    marker = usage.context.set(None)
    try:
        with pytest.raises(HTTPException) as error:
            asyncio.run(fish_audio.transcribe(b'fixture'))
        assert error.value.status_code == 403
    finally:
        usage.context.reset(marker)
    provider.assert_not_called()


def test_operator_initialization_cannot_reset_an_existing_budget(store):
    from manage_public_usage import manage
    store.hset(usage.PREFIX + 'budget', 'used', 7)
    assert asyncio.run(manage('initialize')) == 'already_initialized'
    assert store.hget(usage.PREFIX + 'budget', 'used') == '7'
    assert asyncio.run(manage('disable')) == 'updated'
    assert store.hget(usage.PREFIX + 'budget', 'enabled') == '0'
    assert store.hget(usage.PREFIX + 'budget', 'used') == '7'


def test_session_issuance_rate_limit(store):
    for _ in range(10):
        visitor('network')
    with pytest.raises(HTTPException) as error:
        visitor('network')
    assert error.value.status_code == 429
    assert store.hget(usage.PREFIX + 'budget', 'used') == '0'


@pytest.mark.parametrize('failure', ['disabled', 'environment', 'missing', 'corrupt', 'outage', 'malformed'])
def test_storage_and_emergency_fail_closed_before_provider(store, monkeypatch, failure):
    token = visitor('network')
    if failure == 'disabled': store.hset(usage.PREFIX + 'budget', 'enabled', '0')
    if failure == 'environment': monkeypatch.setenv('PUBLIC_GENERATIONS_ENABLED', 'false')
    if failure == 'missing': store.delete(usage.PREFIX + 'budget')
    if failure == 'corrupt': store.hset(usage.PREFIX + 'budget', 'used', 'bad')
    if failure in ('outage', 'malformed'):
        async def command(*args):
            if failure == 'outage': raise HTTPException(503, 'Storage unavailable')
            return {'unexpected': True}
        monkeypatch.setattr(usage, 'command', command)
    provider = AsyncMock(side_effect=AssertionError('Provider must not be called'))
    monkeypatch.setattr(httpx.AsyncClient, 'post', provider)
    marker = usage.context.set((token, 'network'))
    try:
        with pytest.raises(HTTPException) as error:
            asyncio.run(fish_audio.transcribe(b'local-fixture'))
        assert error.value.status_code == 503
    finally:
        usage.context.reset(marker)
    provider.assert_not_called()


def test_direct_api_requires_real_session_even_with_old_demo_token(store, monkeypatch):
    monkeypatch.setenv('DEMO_ACCESS_TOKEN', 'old-demo-token-at-least-32-characters')
    provider = AsyncMock(side_effect=AssertionError('No provider'))
    monkeypatch.setattr(fish_audio, 'generate', provider)
    with TestClient(main.app, client=('192.0.2.10', 1234)) as client:
        for path in ('/api/preview', '/api/transcribe'):
            assert client.post(path, json={}, headers={'Authorization': 'Bearer old-demo-token-at-least-32-characters'}).status_code == 401
            assert client.post(path, json={}, headers={'X-Visitor-Session': 'fabricated'}).status_code == 401
        session = client.post('/api/public/session').json()
        assert session['remaining'] == 2
        headers = {'X-Visitor-Session': session['session_token']}
        assert client.get('/api/public/usage', headers=headers).json()['remaining'] == 2
        assert client.post('/api/preview', json={}, headers=headers).status_code == 422
    provider.assert_not_called()


def test_ip_headers_are_not_trusted_locally_and_ipv6_is_grouped(store, monkeypatch):
    def req(host, headers=()):
        return Request({'type': 'http', 'client': (host, 123), 'headers': headers})
    assert usage.ip_key(req('192.0.2.10')) == usage.ip_key(req('192.0.2.10', [(b'x-forwarded-for', b'1.2.3.4')]))
    assert usage.ip_key(req('2001:db8::1')) == usage.ip_key(req('2001:db8::2'))
    monkeypatch.setenv('PUBLIC_IP_SOURCE', 'render')
    monkeypatch.setenv('RENDER', 'true')
    monkeypatch.setenv('PUBLIC_RENDER_IP_VERIFIED', 'true')
    with pytest.raises(HTTPException): usage.ip_key(req('192.0.2.10'))
    assert usage.ip_key(req('192.0.2.10', [(b'true-client-ip', b'198.51.100.1')])) != usage.ip_key(req('192.0.2.10', [(b'true-client-ip', b'198.51.100.2')]))


def test_provider_failure_and_retry_each_consume_a_reservation(store, monkeypatch):
    token = visitor('network')
    calls = []
    async def handler(request):
        calls.append(request.url.path)
        return httpx.Response(503)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    marker = usage.context.set((token, 'network'))
    try:
        with pytest.raises(fish_audio.FishError):
            asyncio.run(fish_audio.generate('Hello', Path('unused'), reference_id='fixture-voice'))
        assert len(calls) == 2
        with pytest.raises(HTTPException):
            asyncio.run(fish_audio.generate('Regenerate', Path('unused'), reference_id='fixture-voice'))
        assert len(calls) == 2
    finally:
        usage.context.reset(marker)
    assert store.hget(usage.PREFIX + 'budget', 'used') == '2'


def test_real_preview_reserves_setup_and_tts_then_preserves_apply_undo_redo_export(store, monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'DATA', tmp_path)
    sessions.clear(); previews.clear()
    calls = []
    clip = wav_bytes(2, 440)
    async def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/model':
            return httpx.Response(201, json={'_id': 'fixture-voice', 'state': 'trained'})
        return httpx.Response(200, content=clip)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    try:
        with TestClient(main.app, client=('192.0.2.20', 123)) as client:
            token = client.post('/api/public/session').json()['session_token']
            client.headers['X-Visitor-Session'] = token
            recording = upload(client).json()
            sid = recording['session_id']
            body = dict(session_id=sid, start=2, end=3, revision=0, replacement_text='Friday')
            response = client.post('/api/preview', json=body)
            assert response.status_code == 200, response.text
            candidate = response.json()
            assert calls == ['/model', '/v1/tts']
            assert client.get('/api/public/usage').json()['remaining'] == 0
            assert client.post('/api/preview', json=body).status_code == 429
            assert len(calls) == 2
            assert client.get(candidate['preview_url']).status_code == 200
            apply = {**body, 'preview_id': candidate['preview_id']}
            assert client.post('/api/replace', json=apply).status_code == 200
            assert client.post(f'/api/undo/{sid}', json={'revision': 1}).status_code == 200
            assert client.post(f'/api/redo/{sid}', json={'revision': 2}).status_code == 200
            assert client.get(f'/api/export/{sid}').status_code == 200
            assert len(calls) == 2
    finally:
        sessions.clear(); previews.clear()


def test_change_delivery_asr_cache_and_tts_share_the_same_budget(store, monkeypatch, tmp_path):
    monkeypatch.setattr(main, 'DATA', tmp_path)
    sessions.clear(); previews.clear()
    calls = []
    clip = wav_bytes(2, 440)
    async def handler(request):
        calls.append(request.url.path)
        if request.url.path == '/v1/asr': return httpx.Response(200, json={'text': 'Welcome everyone.'})
        assert request.headers['model'] == 'drama-3'
        return httpx.Response(200, content=clip)
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    try:
        with TestClient(main.app, client=('192.0.2.21', 123)) as client:
            client.headers['X-Visitor-Session'] = client.post('/api/public/session').json()['session_token']
            sid = upload(client).json()['session_id']
            region = dict(session_id=sid, revision=0, start=2, end=3)
            assert client.post('/api/transcribe', json=region).status_code == 200
            assert client.post('/api/transcribe', json=region).json()['cached'] is True
            response = client.post('/api/preview', json={**region, 'mode': 'delivery', 'replacement_text': 'Welcome everyone.',
                'segment_text': 'Welcome everyone.', 'direction': 'excited', 'reference_text': 'exact fixture reference'})
            assert response.status_code == 200, response.text
            assert calls == ['/v1/asr', '/v1/tts']
            assert client.get('/api/public/usage').json()['remaining'] == 0
    finally:
        sessions.clear(); previews.clear()


def test_emergency_switch_between_provider_operations_stops_next_call(store, monkeypatch, tmp_path):
    token = visitor('network')
    calls = []
    async def handler(request):
        calls.append(request.url.path)
        store.hset(usage.PREFIX + 'budget', 'enabled', 0)
        return httpx.Response(201, json={'_id': 'fixture', 'state': 'trained'})
    reference = tmp_path / 'reference.wav'
    reference.write_bytes(b'local fixture')
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    marker = usage.context.set((token, 'network'))
    try:
        asyncio.run(fish_audio.create_voice(reference, 'fixture'))
        with pytest.raises(HTTPException):
            asyncio.run(fish_audio.generate('Hello', reference, reference_id='fixture'))
        assert calls == ['/model']
    finally:
        usage.context.reset(marker)


@pytest.mark.parametrize('response', [httpx.Response(500), httpx.Response(200, json={'error': 'private internal error'}),
                                     httpx.Response(200, json=[]), httpx.Response(200, content=b'invalid json')])
def test_rest_storage_errors_are_safe_and_not_retried(monkeypatch, response):
    monkeypatch.setenv('UPSTASH_REDIS_REST_URL', 'https://storage-fixture.invalid')
    monkeypatch.setenv('UPSTASH_REDIS_REST_TOKEN', 'private-token')
    calls = []
    def handler(request):
        calls.append(request)
        return response
    real_client = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: real_client(transport=httpx.MockTransport(handler), **kwargs))
    with pytest.raises(HTTPException) as error:
        asyncio.run(usage.command('GET', 'fixture'))
    assert error.value.status_code == 503
    assert 'private' not in error.value.detail
    assert len(calls) == 1
