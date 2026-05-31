"""
conftest.py — loaded by pytest before test collection.

Stubs out asyncpg (C extension that may not be installed locally) and the
database engine so unit tests can import app modules without a running
PostgreSQL instance.
"""
import sys
from unittest.mock import MagicMock, patch

# ── 1. Stub asyncpg (C extension, not available outside Docker) ──────────────
_asyncpg_mock = MagicMock()
for _mod in [
    "asyncpg",
    "asyncpg.pgproto",
    "asyncpg.pgproto.pgproto",
    "asyncpg.protocol",
    "asyncpg.connection",
    "asyncpg.pool",
    "asyncpg.exceptions",
]:
    sys.modules[_mod] = _asyncpg_mock

# ── 2. Patch create_async_engine so database.py doesn't try to connect ───────
# Must be done BEFORE app.database is first imported.
_engine_mock = MagicMock()
_session_factory_mock = MagicMock()

patch("sqlalchemy.ext.asyncio.create_async_engine", return_value=_engine_mock).start()
patch("sqlalchemy.ext.asyncio.async_sessionmaker", return_value=_session_factory_mock).start()

# ── 3. Force app.database import now (with patches active) ───────────────────
import app.database  # noqa: E402

app.database.engine = _engine_mock
app.database.AsyncSessionLocal = _session_factory_mock

# ── 4. Clear settings cache so each test module gets a clean settings object ─
import app.config  # noqa: E402

app.config.get_settings.cache_clear()
