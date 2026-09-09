import pytest


@pytest.fixture(autouse=True)
def reset_schedulers():
    from app.domain.server import Server
    Server._schedulers.clear()
    yield
    Server._schedulers.clear()
