"""Test-wide environment defaults.

app.config.Settings has required fields with no defaults and is instantiated
at import time by app modules, so collecting any test that imports app code
fails in environments without a .env (e.g. bare CI runners or fresh clones).
Provide inert placeholders BEFORE any app import. setdefault keeps real
environment variables (like CI's) authoritative; note that os.environ takes
precedence over .env in pydantic-settings, so under pytest the app always
sees these dummies — unit tests must not depend on real credentials anyway.
"""

import os

_TEST_ENV_DEFAULTS = {
    "DATABASE_URL": "postgresql://test:test@localhost:5432/test",
    "REDIS_URL": "redis://localhost:6379/0",
    "SECRET_KEY": "test-secret-key",
    "YOUTUBE_CLIENT_ID": "test-client-id.apps.googleusercontent.com",
    "YOUTUBE_CLIENT_SECRET": "test-client-secret",
    "OPENAI_API_KEY": "sk-test-not-a-real-key",
}

for _key, _value in _TEST_ENV_DEFAULTS.items():
    os.environ.setdefault(_key, _value)
