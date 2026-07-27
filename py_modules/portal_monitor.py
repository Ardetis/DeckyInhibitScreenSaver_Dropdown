from typing import Any, Callable, Dict

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus


class PortalInhibitMonitor:
    INHIBIT_INTERFACE = "org.freedesktop.portal.Inhibit"
    REQUEST_INTERFACE = "org.freedesktop.portal.Request"

    def __init__(self, log: Callable[[str], None], on_event: Callable[..., None] = None):
        self._log = log
        self._on_event = on_event
        self._bus = None

    @staticmethod
    def _option_value(options: Dict[str, Any], key: str, default: Any = None) -> Any:
        value = options.get(key)
        return getattr(value, "value", default) if value is not None else default

    def _handle_message(self, message: Message) -> None:
        if message.message_type != MessageType.METHOD_CALL:
            return

        if message.interface == self.INHIBIT_INTERFACE and message.member == "Inhibit":
            application = message.body[0] if len(message.body) > 0 else ""
            flags = message.body[1] if len(message.body) > 1 else 0
            options = message.body[2] if len(message.body) > 2 else {}
            reason = self._option_value(options, "reason", "")
            handle_token = self._option_value(options, "handle_token", "")
            self._log(
                f'[portal] inhibit sender={message.sender} application={application!r} '
                f'flags={flags} reason={reason!r} handle_token={handle_token!r}'
            )
            if self._on_event is not None:
                self._on_event("inhibit", message.sender, application, reason)
            return

        if message.interface == self.REQUEST_INTERFACE and message.member == "Close":
            self._log(
                f'[portal] request closed sender={message.sender} path={message.path}'
            )

            if self._on_event is not None:
                self._on_event("close", message.sender, message.path)
    async def start(self) -> None:
        if self._bus is not None:
            return

        monitor_bus = await MessageBus().connect()
        monitor_bus.add_message_handler(self._handle_message)
        reply = await monitor_bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus.Monitoring",
                member="BecomeMonitor",
                signature="asu",
                body=[
                    [
                        "type='method_call',interface='org.freedesktop.portal.Inhibit'",
                        "type='method_call',interface='org.freedesktop.portal.Request',member='Close'",
                    ],
                    0,
                ],
            )
        )
        if reply.message_type == MessageType.ERROR:
            monitor_bus.disconnect()
            raise RuntimeError(f'Unable to monitor portal inhibition: {reply.body}')

        self._bus = monitor_bus
        self._log('[portal] inhibit monitor started')

    async def stop(self) -> None:
        if self._bus is None:
            return
        self._bus.disconnect()
        self._bus = None
        self._log('[portal] inhibit monitor stopped')