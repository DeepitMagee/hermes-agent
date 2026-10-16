"""ACP ``session/set_model`` on the gateway path: the advertised ``provider:model`` id switches the
session's provider too (#139165, #134889 MP-10), over the real ACP stdio wire and a real gateway."""
import asyncio
import json
import threading

import pytest

from tests.acp_adapter.test_gateway_sessions import editor, viewer
from tests.waiting import async_wait_until

_SECOND = {'providers': {'second': {'name': 'second', 'base_url': 'http://127.0.0.1:9/v1',
                                    'api_key': 'loopback-only', 'default_model': 'second-model'}}}


def _second_on_peer(daemon, model_peer):
    """Point the named provider at the loopback peer (the daemon reads config per resolve)."""
    home = daemon[0]
    config = json.loads((home / 'config.yaml').read_text())
    config['providers']['second']['base_url'] = f'http://127.0.0.1:{model_peer.server_port}/second/v1'
    (home / 'config.yaml').write_text(json.dumps(config))


@pytest.mark.platforms('linux')
@pytest.mark.asyncio
@pytest.mark.parametrize('daemon', [_SECOND], indirect=True)
async def test_cross_provider_pick_switches_provider_and_runs_the_next_turn_there(daemon, tmp_path, model_peer):
    _second_on_peer(daemon, model_peer)
    async with viewer(daemon) as ws:
        sid = (await ws.rpc('session.create', request_id='acp-pick', source='cli', cwd=str(tmp_path)))['session_id']
        async with editor(daemon, tmp_path) as acp:
            await acp.rpc('initialize', protocolVersion=1, clientCapabilities={})
            assert 'result' in await acp.rpc('session/load', cwd=str(tmp_path), sessionId=sid, mcpServers=[])
            picked = await acp.rpc('session/set_model', sessionId=sid, modelId='custom:second:second-model')
            assert 'result' in picked, picked
            info = await ws.rpc('session.info', session_id=sid)
            assert (info.get('provider'), info.get('model')) == ('custom:second', 'second-model'), info
            turn = await acp.rpc('session/prompt', sessionId=sid, prompt=[{'type': 'text', 'text': 'WS_SHARED pick'}])
            assert turn['result']['stopReason'] == 'end_turn', turn
            assert model_peer.requests[-1]['model'] == 'second-model', model_peer.requests[-1]


def _shown(frames, start=0):
    return "".join(f["params"]["update"]["content"]["text"] for f in frames[start:]
                   if f.get("method") == "session/update"
                   and f["params"]["update"].get("sessionUpdate") == "agent_message_chunk")


async def _pick_during_a_turn(acp, sid, model_peer):
    model_peer.blocked, model_peer.release = threading.Event(), threading.Event()
    running = asyncio.create_task(acp.rpc('session/prompt', sessionId=sid,
                                          prompt=[{'type': 'text', 'text': 'WS_SHARED BLOCK_FIFO'}]))
    await asyncio.to_thread(model_peer.blocked.wait, 30)
    start = len(acp.frames)
    picked = await acp.rpc('session/set_model', sessionId=sid, modelId='custom:second:second-model')
    assert 'result' in picked, picked
    return running, start


@pytest.mark.platforms('linux')
@pytest.mark.asyncio
@pytest.mark.parametrize('daemon', [_SECOND], indirect=True)
async def test_pick_during_a_turn_says_it_applies_next_and_lands_there(daemon, tmp_path, model_peer):
    _second_on_peer(daemon, model_peer)
    async with viewer(daemon) as ws:
        sid = (await ws.rpc('session.create', request_id='acp-defer', source='cli', cwd=str(tmp_path)))['session_id']
        async with editor(daemon, tmp_path) as acp:
            await acp.rpc('initialize', protocolVersion=1, clientCapabilities={})
            assert 'result' in await acp.rpc('session/load', cwd=str(tmp_path), sessionId=sid, mcpServers=[])
            running, start = await _pick_during_a_turn(acp, sid, model_peer)
            assert 'second-model applies from your next message' in _shown(acp.frames, start), acp.frames[start:]
            model_peer.release.set()
            assert (await running)['result']['stopReason'] == 'end_turn'
            assert model_peer.requests[-1]['model'] == 'local-wire-stub'  # the running turn kept its model
            turn = await acp.rpc('session/prompt', sessionId=sid, prompt=[{'type': 'text', 'text': 'WS_SHARED next'}])
            assert turn['result']['stopReason'] == 'end_turn', turn
            assert model_peer.requests[-1]['model'] == 'second-model', model_peer.requests[-1]


@pytest.mark.platforms('linux')
@pytest.mark.asyncio
@pytest.mark.parametrize('daemon', [_SECOND], indirect=True)
async def test_deferred_pick_that_no_longer_resolves_is_named_to_the_editor(daemon, tmp_path, model_peer):
    _second_on_peer(daemon, model_peer)
    home = daemon[0]
    async with viewer(daemon) as ws:
        sid = (await ws.rpc('session.create', request_id='acp-refuse', source='cli', cwd=str(tmp_path)))['session_id']
        async with editor(daemon, tmp_path) as acp:
            await acp.rpc('initialize', protocolVersion=1, clientCapabilities={})
            assert 'result' in await acp.rpc('session/load', cwd=str(tmp_path), sessionId=sid, mcpServers=[])
            running, start = await _pick_during_a_turn(acp, sid, model_peer)
            # The picked provider is removed before the boundary: the pick cannot land.
            config = json.loads((home / 'config.yaml').read_text())
            config.pop('providers')
            (home / 'config.yaml').write_text(json.dumps(config))
            model_peer.release.set()
            assert (await running)['result']['stopReason'] == 'end_turn'
            turn = await acp.rpc('session/prompt', sessionId=sid, prompt=[{'type': 'text', 'text': 'WS_SHARED next'}])
            assert turn['result']['stopReason'] == 'end_turn', turn
            await async_wait_until(lambda: 'was not applied' in _shown(acp.frames, start), timeout=15,
                                   what='the named refusal of the deferred pick')
            shown = _shown(acp.frames, start)
            assert 'second-model was not applied' in shown and 'local-wire-stub' in shown, shown
            assert model_peer.requests[-1]['model'] == 'local-wire-stub', model_peer.requests[-1]
