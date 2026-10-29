import pytest
from app import public_usage


@pytest.fixture(autouse=True)
def legacy_adapter_access(request, monkeypatch):
    """Old adapter unit tests run in an explicitly authorized demo context.

    Public-budget tests exercise the real guards and real Lua without this fixture.
    """
    if request.node.path.name == 'test_public_usage.py':
        yield
        return
    monkeypatch.setenv('AI_ACCESS_MODE', 'demo')
    marker = public_usage.context.set('demo')
    yield
    public_usage.context.reset(marker)
