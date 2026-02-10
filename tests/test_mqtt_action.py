"""
Tests for the @mqtt_action decorator and auto-generated master command handler.
"""
import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from petal_app_manager.plugins.base import Petal
from petal_app_manager.plugins.decorators import mqtt_action


# ─── Test Petal fixtures ────────────────────────────────────────────────────

class SamplePetal(Petal):
    """A minimal petal that uses @mqtt_action."""
    name = "test-petal"
    version = "0.1.0"

    @mqtt_action(command="light_action")
    async def handle_light(self, topic: str, message: dict):
        self._call_log.append(("light", topic, message))

    @mqtt_action(command="heavy_action", cpu_heavy=True)
    async def handle_heavy(self, topic: str, message: dict):
        self._call_log.append(("heavy", topic, message))

    def startup(self):
        super().startup()
        self._call_log = []


class EmptyPetal(Petal):
    """A petal with no @mqtt_action methods."""
    name = "empty-petal"
    version = "0.1.0"


# ─── Decorator metadata tests ──────────────────────────────────────────────

def test_mqtt_action_sets_metadata():
    """@mqtt_action should attach __mqtt_action__ with command and cpu_heavy."""
    petal = SamplePetal()
    meta_light = petal.handle_light.__mqtt_action__
    meta_heavy = petal.handle_heavy.__mqtt_action__

    assert meta_light["command"] == "light_action"
    assert meta_light["cpu_heavy"] is False

    assert meta_heavy["command"] == "heavy_action"
    assert meta_heavy["cpu_heavy"] is True


def test_mqtt_action_default_cpu_heavy_is_false():
    """cpu_heavy should default to False."""
    @mqtt_action(command="some_cmd")
    async def handler(self, topic, msg):
        pass
    assert handler.__mqtt_action__["cpu_heavy"] is False


# ─── collect / has helpers ──────────────────────────────────────────────────

def test_has_mqtt_actions_true():
    petal = SamplePetal()
    assert petal.has_mqtt_actions() is True


def test_has_mqtt_actions_false():
    petal = EmptyPetal()
    assert petal.has_mqtt_actions() is False


def test_collect_mqtt_actions():
    """_collect_mqtt_actions builds the correct handler/cpu_heavy dicts."""
    petal = SamplePetal()
    handlers, cpu_flags = petal._collect_mqtt_actions()

    assert "test-petal/light_action" in handlers
    assert "test-petal/heavy_action" in handlers

    assert cpu_flags["test-petal/light_action"] is False
    assert cpu_flags["test-petal/heavy_action"] is True


# ─── Master handler dispatch tests ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_master_handler_dispatches_light():
    """Light command should be dispatched directly (no offloading)."""
    petal = SamplePetal()
    petal.startup()

    # Build handler table
    handlers, cpu_flags = petal._collect_mqtt_actions()
    petal._mqtt_command_handlers = handlers
    petal._mqtt_cpu_heavy_commands = cpu_flags

    mock_proxy = MagicMock()
    petal._proxies = {"mqtt": mock_proxy}

    await petal._mqtt_master_command_handler(
        "some/topic",
        {"command": "test-petal/light_action", "payload": {"x": 1}},
    )

    assert len(petal._call_log) == 1
    assert petal._call_log[0][0] == "light"


@pytest.mark.asyncio
async def test_master_handler_dispatches_heavy():
    """Heavy command should be dispatched via run_in_executor offloading."""
    petal = SamplePetal()
    petal.startup()

    handlers, cpu_flags = petal._collect_mqtt_actions()
    petal._mqtt_command_handlers = handlers
    petal._mqtt_cpu_heavy_commands = cpu_flags

    mock_proxy = MagicMock()
    petal._proxies = {"mqtt": mock_proxy}
    petal._loop = asyncio.get_running_loop()

    await petal._mqtt_master_command_handler(
        "some/topic",
        {"command": "test-petal/heavy_action", "payload": {"x": 2}},
    )

    assert len(petal._call_log) == 1
    assert petal._call_log[0][0] == "heavy"


@pytest.mark.asyncio
async def test_master_handler_unknown_command_for_petal():
    """Unknown command matching petal prefix should send error response."""
    petal = SamplePetal()
    petal.startup()

    handlers, cpu_flags = petal._collect_mqtt_actions()
    petal._mqtt_command_handlers = handlers
    petal._mqtt_cpu_heavy_commands = cpu_flags

    mock_proxy = MagicMock()
    mock_proxy.send_command_response = AsyncMock()
    petal._proxies = {"mqtt": mock_proxy}

    await petal._mqtt_master_command_handler(
        "some/topic",
        {
            "command": "test-petal/nonexistent",
            "waitResponse": True,
            "messageId": "msg-123",
        },
    )

    # Should have sent an error response
    mock_proxy.send_command_response.assert_awaited_once()
    call_kwargs = mock_proxy.send_command_response.call_args
    assert call_kwargs.kwargs["response_data"]["error_code"] == "UNKNOWN_COMMAND"
    assert "test-petal/light_action" in call_kwargs.kwargs["response_data"]["available_commands"]


@pytest.mark.asyncio
async def test_master_handler_ignores_other_petal_commands():
    """Commands not matching petal prefix should be silently ignored."""
    petal = SamplePetal()
    petal.startup()

    handlers, cpu_flags = petal._collect_mqtt_actions()
    petal._mqtt_command_handlers = handlers
    petal._mqtt_cpu_heavy_commands = cpu_flags

    mock_proxy = MagicMock()
    mock_proxy.send_command_response = AsyncMock()
    petal._proxies = {"mqtt": mock_proxy}

    await petal._mqtt_master_command_handler(
        "some/topic",
        {"command": "other-petal/some_action"},
    )

    # Should NOT have called any handler or sent error response
    assert len(petal._call_log) == 0
    mock_proxy.send_command_response.assert_not_awaited()


@pytest.mark.asyncio
async def test_master_handler_not_initialized():
    """Master handler should warn when handlers not yet built."""
    petal = SamplePetal()
    petal.startup()
    # Do NOT build handlers

    mock_proxy = MagicMock()
    petal._proxies = {"mqtt": mock_proxy}

    # Should not raise, just warn
    await petal._mqtt_master_command_handler(
        "some/topic",
        {"command": "test-petal/light_action"},
    )

    assert len(petal._call_log) == 0


# ─── _setup_mqtt_actions integration ───────────────────────────────────────

@pytest.mark.asyncio
async def test_setup_mqtt_actions_registers_handler():
    """_setup_mqtt_actions should call mqtt_proxy.register_handler."""
    petal = SamplePetal()
    petal.startup()

    mock_proxy = MagicMock()
    mock_proxy.register_handler = MagicMock(return_value="sub-id-999")
    petal._proxies = {"mqtt": mock_proxy}

    sub_id = await petal._setup_mqtt_actions()

    assert sub_id == "sub-id-999"
    mock_proxy.register_handler.assert_called_once()
    # The registered handler should be the master handler
    registered_fn = mock_proxy.register_handler.call_args[0][0]
    assert registered_fn == petal._mqtt_master_command_handler


@pytest.mark.asyncio
async def test_setup_mqtt_actions_no_actions():
    """_setup_mqtt_actions should return None for petals with no @mqtt_action."""
    petal = EmptyPetal()

    mock_proxy = MagicMock()
    petal._proxies = {"mqtt": mock_proxy}

    sub_id = await petal._setup_mqtt_actions()

    assert sub_id is None
    mock_proxy.register_handler.assert_not_called()
