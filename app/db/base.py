"""Centralized SQLModel imports to ensure metadata is populated."""

# Backend models
from app.backend.models import user as _user  # noqa: F401
from app.backend.models import task as _task  # noqa: F401
from app.backend.models import refresh_token as _refresh_token  # noqa: F401
from app.backend.models import emotion as _emotion  # noqa: F401

# Analyze models
from app.analyze import models as _analyze_models  # noqa: F401
