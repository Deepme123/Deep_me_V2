from app.db.session import engine, get_session as _get_session


def get_db():
    yield from _get_session()


def get_session():
    """Backward-compatible alias."""
    yield from _get_session()
