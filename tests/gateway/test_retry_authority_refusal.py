"""Messaging /retry under a session authority answers the authority's admission refusals BEFORE
it rewrites the transcript (#139257).

The re-sent turn is admitted by the routed profile's authority (``admit_native``). A draining or
retiring runtime refuses it with ``runtime_draining`` and a full FIFO with ``queue_full``; both
landed after ``rewrite_transcript`` had already dropped the last exchange, so every refused /retry
lost a turn (and the next /retry ate the one before it). Real authority, real SQLite; only the
turn handler is replaced by a recorder.
"""
import weakref
from pathlib import Path

import pytest

from gateway.config import GatewayConfig, Platform
from gateway.platforms.event import MessageEvent, MessageType
from gateway.run import GatewayRunner
from gateway.run_runtime import initialize_gateway_runtime
from gateway.runtime_ownership import process_ownership
from gateway.session import SessionSource
from gateway.session_ingress_context import native_callback, register_transport_home


class _FakeAdapter:
    pass


@pytest.fixture
def served(tmp_path, monkeypatch):
    root = tmp_path / '.hermes'
    root.mkdir(mode=0o700)
    monkeypatch.setattr(Path, 'home', lambda: tmp_path)
    monkeypatch.setenv('HERMES_HOME', str(root))
    import hermes_state
    monkeypatch.setattr(hermes_state, 'DEFAULT_DB_PATH', hermes_state._IMPORT_DEFAULT_DB_PATH)
    homes = [('default', root)]
    config = GatewayConfig()
    config._runtime_profile_homes = tuple(homes)
    runner = GatewayRunner(config)
    process_ownership.reserve([home for _, home in homes])
    yield runner, root
    for authority in list(getattr(runner, 'session_authorities', []) or []):
        authority.db.close()
    for _, home in homes:
        process_ownership.release(home)


async def _exchange(runner, root):
    await initialize_gateway_runtime(runner)
    register_transport_home(runner, None, root)
    adapter = _FakeAdapter()
    runner.adapters = {Platform.DISCORD: adapter}
    runner._is_user_authorized_for_source = lambda *a, **k: True
    source = SessionSource(platform=Platform.DISCORD, chat_id='c1', chat_type='dm',
                           user_id='u1', user_name='probe')
    source._transport_adapter_ref = weakref.ref(adapter)
    entry = await runner.async_session_store.get_or_create_session(source)
    runner.session_store.append_to_transcript(entry.session_id, {'role': 'user', 'content': 'retry me'})
    runner.session_store.append_to_transcript(entry.session_id, {'role': 'assistant', 'content': 'old answer'})
    sent = []

    async def recorder(event):
        sent.append(event.text)
        return 'resent'
    runner._handle_message = recorder
    return source, entry.session_id, sent


async def _retry(runner, root, source):
    event = MessageEvent(text='/retry', message_type=MessageType.TEXT, source=source, message_id='m-retry')
    with native_callback(runner, event, root, None):
        return await runner._handle_retry_command(event)


def _contents(runner, sid):
    return [m.get('content') for m in runner.session_store.load_transcript(sid)]


@pytest.mark.asyncio
async def test_retry_into_a_draining_authority_keeps_the_exchange(served):
    runner, root = served
    source, sid, sent = await _exchange(runner, root)
    runner._draining = True

    reply = await _retry(runner, root, source)

    assert sent == [], 'the re-send ran into a draining authority'
    assert reply and '⏳' in reply
    assert _contents(runner, sid) == ['retry me', 'old answer']


@pytest.mark.asyncio
async def test_retry_into_a_full_fifo_keeps_the_exchange(served, monkeypatch):
    runner, root = served
    source, sid, sent = await _exchange(runner, root)
    import hermes_state_runtime
    monkeypatch.setattr(hermes_state_runtime, 'ADMISSION_QUEUE_MAX', 0)

    reply = await _retry(runner, root, source)

    assert sent == []
    assert reply and 'waiting' in reply
    assert _contents(runner, sid) == ['retry me', 'old answer']


@pytest.mark.asyncio
async def test_an_admissible_retry_still_replaces_the_exchange_once(served):
    runner, root = served
    source, sid, sent = await _exchange(runner, root)

    reply = await _retry(runner, root, source)

    assert reply == 'resent'
    assert sent == ['retry me']
    assert _contents(runner, sid) == []
