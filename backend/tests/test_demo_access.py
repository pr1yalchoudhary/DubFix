from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from app import main, fish_audio


@pytest.mark.parametrize('path', ['/api/preview', '/api/transcribe'])
def test_paid_routes_fail_closed(path, monkeypatch):
    generate = AsyncMock(side_effect=AssertionError('Provider must not be called'))
    transcribe = AsyncMock(side_effect=AssertionError('Provider must not be called'))
    create_voice = AsyncMock(side_effect=AssertionError('Provider must not be called'))
    monkeypatch.setattr(fish_audio, 'generate', generate)
    monkeypatch.setattr(fish_audio, 'transcribe', transcribe)
    monkeypatch.setattr(fish_audio, 'create_voice', create_voice)
    with TestClient(main.app) as client:
        monkeypatch.delenv('DEMO_ACCESS_TOKEN', raising=False)
        assert client.post(path, json={}).status_code == 503
        monkeypatch.setenv('DEMO_ACCESS_TOKEN', 'short')
        assert client.post(path, json={}).status_code == 503
        token = 'test-only-random-secret-at-least-32-characters'
        monkeypatch.setenv('DEMO_ACCESS_TOKEN', token)
        for headers in ({}, {'Authorization': 'Bearer wrong'}, {'Authorization': 'Basic ' + token}):
            assert client.post(path, json={}, headers=headers).status_code == 401
        # Authentication passes; invalid body is then rejected before any provider call.
        assert client.post(path, json={}, headers={'Authorization': 'Bearer ' + token}).status_code == 422
        assert client.get('/api/health').status_code == 200
    generate.assert_not_called()
    transcribe.assert_not_called()
    create_voice.assert_not_called()


def test_cors_allows_deployed_and_local_frontends_only():
    with TestClient(main.app) as client:
        for origin in ('https://tweeq-ruby.vercel.app', 'http://localhost:5173', 'http://127.0.0.1:5173'):
            response = client.options('/api/preview', headers={'Origin': origin,
                'Access-Control-Request-Method': 'POST',
                'Access-Control-Request-Headers': 'authorization,content-type'})
            assert response.status_code == 200
            assert response.headers['access-control-allow-origin'] == origin
        response = client.options('/api/preview', headers={'Origin': 'https://untrusted.example',
            'Access-Control-Request-Method': 'POST'})
        assert 'access-control-allow-origin' not in response.headers
