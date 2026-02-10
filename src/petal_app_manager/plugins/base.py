from abc import ABC
from typing import Mapping, Dict, Any, Callable, Optional, List, Tuple
import asyncio
import inspect

from fastapi.templating import Jinja2Templates
from ..proxies.base import BaseProxy

import logging

logger = logging.getLogger("PluginsLoader")

class Petal(ABC):
    """
    Petal authors only inherit this; NO FastAPI import, no routers.
    """
    name: str
    version: str

    def __init__(self) -> None:
        self._proxies: Mapping[str, BaseProxy] = {}
        # Populated by _collect_mqtt_actions() during startup
        self._mqtt_command_handlers: Optional[Dict[str, Callable]] = None
        self._mqtt_cpu_heavy_commands: Optional[Dict[str, bool]] = None

    # define a startup method that can be overridden
    def startup(self) -> None:
        """
        Called when the petal is started.
        """
        logger.info(f"Starting petal {self.name} ({self.version})")
        pass

    def shutdown(self) -> None:
        """
        Called when the petal is stopped.
        """
        logger.info(f"Shutting down petal {self.name} ({self.version})")
        pass

    async def async_startup(self) -> None:
        """
        Called after startup to handle async operations like MQTT subscriptions.
        """
        logger.info(f"Starting async operations for petal {self.name} ({self.version})")
        pass

    async def async_shutdown(self) -> None:
        """
        Called before shutdown to handle async operations like MQTT unsubscriptions.
        """
        logger.info(f"Shutting down async operations for petal {self.name} ({self.version})")
        pass

    def inject_proxies(self, proxies: Mapping[str, BaseProxy]) -> None:
        # Skip isinstance check for now due to import issues
        # TODO: Debug why isinstance(proxy, BaseProxy) fails during app startup
        self._proxies = proxies

    def inject_templates(self, templates: Mapping[str, Jinja2Templates]) -> None:
        """
        Inject Jinja2 templates into the petal.
        """
        self.templates = templates

    # ────────────────────────── MQTT command handler scaffolding ──────────────

    def _collect_mqtt_actions(self) -> Tuple[Dict[str, Callable], Dict[str, bool]]:
        """Scan ``self`` for methods decorated with ``@mqtt_action`` and build
        two parallel dicts keyed by the fully-qualified command string
        (``"{petal_name}/{command_suffix}"``):

        * **handlers** – the async method reference
        * **cpu_heavy** – whether the handler should be offloaded

        Returns ``(handlers, cpu_heavy_flags)``.
        """
        handlers: Dict[str, Callable] = {}
        cpu_heavy_flags: Dict[str, bool] = {}

        for attr_name in dir(self):
            try:
                attr = getattr(self, attr_name)
            except Exception:
                continue
            meta = getattr(attr, "__mqtt_action__", None)
            if meta is None:
                continue
            command_suffix = meta["command"]
            full_command = f"{self.name}/{command_suffix}"
            handlers[full_command] = attr
            cpu_heavy_flags[full_command] = meta.get("cpu_heavy", False)

        return handlers, cpu_heavy_flags

    def has_mqtt_actions(self) -> bool:
        """Return ``True`` if any method is decorated with ``@mqtt_action``."""
        for attr_name in dir(self):
            try:
                attr = getattr(self, attr_name)
            except Exception:
                continue
            if getattr(attr, "__mqtt_action__", None) is not None:
                return True
        return False

    async def _mqtt_master_command_handler(self, topic: str, message: Dict[str, Any]):
        """Auto-generated master command handler that dispatches to
        ``@mqtt_action``-decorated methods.

        This is the single handler registered with the MQTT proxy.
        It reads the ``command`` field from the incoming message and looks
        up the matching handler in ``self._mqtt_command_handlers``.

        If the target handler is marked ``cpu_heavy``, the dispatch info
        is stored on the message so the proxy can offload it.
        """
        mqtt_proxy = self._proxies.get("mqtt")

        try:
            if self._mqtt_command_handlers is None:
                logger.warning(
                    "Petal %s not fully initialized yet, MQTT command handlers not available",
                    self.name,
                )
                return

            # Guard: ensure MQTT topics are fully initialised (org ID available)
            if mqtt_proxy is not None and getattr(mqtt_proxy, "organization_id", None) is None:
                logger.warning(
                    "Petal %s MQTT topics not yet initialized (organization_id missing), "
                    "cannot process commands",
                    self.name,
                )
                return

            command = message.get("command", "")
            logger.info("Petal %s master handler received command: %s", self.name, command)

            if command in self._mqtt_command_handlers:
                handler = self._mqtt_command_handlers[command]
                is_cpu_heavy = self._mqtt_cpu_heavy_commands.get(command, False)

                if is_cpu_heavy and self._loop and not self._loop.is_closed():
                    # Offload CPU-heavy handler to thread pool
                    await self._loop.run_in_executor(
                        None, lambda: asyncio.run(handler(topic, message))
                    )
                else:
                    await handler(topic, message)
            else:
                # Ignore commands not meant for this petal
                if not command.startswith(f"{self.name}/"):
                    logger.debug("Ignoring command not meant for petal %s: %s", self.name, command)
                    return

                error_msg = f"Unknown command: {command}"
                logger.error(error_msg)

                if message.get("waitResponse", False) and mqtt_proxy:
                    await mqtt_proxy.send_command_response(
                        message_id=message.get("messageId", "unknown"),
                        response_data={
                            "status": "error",
                            "message": error_msg,
                            "error_code": "UNKNOWN_COMMAND",
                            "available_commands": list(self._mqtt_command_handlers.keys()),
                        },
                    )

        except Exception as exc:
            error_msg = f"Master command handler error: {exc}"
            logger.error(error_msg)
            try:
                message_id = message.get("messageId", "unknown")
                if message.get("waitResponse", False) and mqtt_proxy:
                    await mqtt_proxy.send_command_response(
                        message_id=message_id,
                        response_data={
                            "status": "error",
                            "message": error_msg,
                            "error_code": "HANDLER_ERROR",
                        },
                    )
            except Exception as resp_exc:
                logger.error("Failed to send error response: %s", resp_exc)

    async def _setup_mqtt_actions(self) -> Optional[str]:
        """Collect ``@mqtt_action``-decorated methods, build the dispatch
        table, and register the master handler with the MQTT proxy.

        Returns the subscription ID on success, ``None`` on failure.
        """
        handlers, cpu_heavy_flags = self._collect_mqtt_actions()
        if not handlers:
            logger.debug("Petal %s has no @mqtt_action handlers", self.name)
            return None

        self._mqtt_command_handlers = handlers
        self._mqtt_cpu_heavy_commands = cpu_heavy_flags

        logger.info(
            "Petal %s registered %d MQTT command(s): %s",
            self.name,
            len(handlers),
            ", ".join(handlers.keys()),
        )

        mqtt_proxy = self._proxies.get("mqtt")
        if mqtt_proxy is None:
            logger.warning("MQTT proxy not available for petal %s", self.name)
            return None

        # Any handler marked cpu_heavy means the *master* handler itself should
        # be marked cpu_heavy=False — the offloading happens *inside* the
        # master handler per-command, not at the proxy level.
        subscription_id = mqtt_proxy.register_handler(self._mqtt_master_command_handler)

        if subscription_id is None:
            logger.error("Failed to register MQTT master handler for petal %s", self.name)
            return None

        logger.info(
            "Petal %s MQTT master handler registered with subscription ID: %s",
            self.name,
            subscription_id,
        )
        return subscription_id