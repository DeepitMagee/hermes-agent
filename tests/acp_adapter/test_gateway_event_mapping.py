"""The gateway's turn events reach the editor as the in-process ACP agent projected them (#134889
ACP-5, ACP-15): native plan updates, the executor's tool verdict, closed tool and permission bubbles,
and ``messageId`` on assistant chunks."""
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from acp.schema import AgentPlanUpdate, AllowedOutcome, DeniedOutcome

from acp_adapter.gateway_server import GatewayACPAgent

TODOS = [{'id': '1', 'content': 'write the test', 'status': 'completed'},
         {'id': '2', 'content': 'fix the bug', 'status': 'in_progress'},
         {'id': '3', 'content': 'drop the hack', 'status': 'cancelled'}]


def agent():
    agent = GatewayACPAgent()
    agent._snapshots['s'] = {}
    agent._gateway = AsyncMock()
    agent._conn = AsyncMock()
    return agent


def updates(agent):
    return [call.kwargs['update'] for call in agent._conn.session_update.await_args_list]


async def project(agent, kind, payload, aid='a'):
    await agent._project({'session_id': 's', 'type': kind, 'admission_id': aid, 'payload': payload})


@pytest.mark.asyncio
async def test_todo_updated_becomes_the_native_plan_update():
    """The owner publishes ``todo.updated`` for a local viewer's turn (an ACP session is LOCAL);
    the in-process agent sent Zed's task panel a ``plan`` update from the todo result."""
    editor = agent()
    await project(editor, 'todo.updated', {'todos': TODOS, 'revision': 2})
    (plan,) = updates(editor)
    assert isinstance(plan, AgentPlanUpdate)
    assert [(e.content, e.status) for e in plan.entries] == [
        ('write the test', 'completed'), ('fix the bug', 'in_progress'), ('[cancelled] drop the hack', 'completed')]


def test_an_acp_session_turn_publishes_todo_updated():
    """The real owner path: a LOCAL (ACP-created) turn's todo tool completion publishes ``todo.updated``."""
    from gateway.config import Platform
    from gateway.run_turn_runner import TurnRunner
    published = []
    turn = object.__new__(TurnRunner)
    turn._ctx = SimpleNamespace(source=SimpleNamespace(platform=Platform.LOCAL, chat_id='chat'),
                                _voice_ack_guild=[None], _native_slack_task_cards=False, progress_mode='all')
    turn._approval_owner = (SimpleNamespace(sessions={'s': SimpleNamespace(tool_progress_mode=None)}), 's', 1)
    turn._publish_execution = lambda kind, payload: published.append((kind, payload)) or True
    turn._publish_api_tool = lambda *a, **k: None
    turn.combined_tool_start_callback('t1', 'todo', {'todos': TODOS})
    turn.combined_tool_complete_callback('t1', 'todo', {'todos': TODOS}, json.dumps({'todos': TODOS, 'revision': 2}))
    assert ('todo.updated', {'todos': TODOS, 'revision': 2}) in published
