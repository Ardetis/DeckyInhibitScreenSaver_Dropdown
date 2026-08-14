import asyncio
from typing import Any, Callable, Dict, List

from dbus_next import Message, MessageType
from dbus_next.aio import MessageBus


class MprisMonitor:
    PLAYER_PREFIX = "org.mpris.MediaPlayer2."
    PLAYER_INTERFACE = "org.mpris.MediaPlayer2.Player"
    PROPERTIES_INTERFACE = "org.freedesktop.DBus.Properties"

    def __init__(self, log: Callable[[str], None], on_event: Callable[..., None] = None):
        self._log = log
        self._on_event = on_event
        self._bus = None
        self._owners: Dict[str, str] = {}
        self._statuses: Dict[str, str] = {}

    @staticmethod
    def _variant_value(value: Any) -> Any:
        return getattr(value, "value", value)

    def _handle_name_owner_changed(self, message: Message) -> None:
        if len(message.body) < 3:
            return
        name, old_owner, new_owner = message.body
        if not name.startswith(self.PLAYER_PREFIX):
            return
        if old_owner:
            self._owners.pop(old_owner, None)
            self._statuses.pop(old_owner, None)
        if new_owner:
            self._owners[new_owner] = name
            self._statuses[new_owner] = "Unknown"
            self._log(f'[mpris] player appeared name={name} owner={new_owner}')
            if self._on_event is not None:
                self._on_event("appeared", name, new_owner)
            if self._bus is not None:
                asyncio.create_task(
                    self._load_playback_status(self._bus, name, new_owner)
                )
        else:
            self._log(f'[mpris] player disappeared name={name} owner={old_owner}')

            if self._on_event is not None:
                self._on_event("disappeared", name, old_owner)
    def _handle_properties_changed(self, message: Message) -> None:
        if len(message.body) < 2 or message.body[0] != self.PLAYER_INTERFACE:
            return
        changed = message.body[1]
        if "PlaybackStatus" not in changed:
            return
        status = self._variant_value(changed["PlaybackStatus"])
        name = self._owners.get(message.sender, "unknown")
        self._statuses[message.sender] = str(status)
        self._log(
            f'[mpris] playback name={name} owner={message.sender} status={status}'
        )
        if self._on_event is not None:
            self._on_event("playback", name, message.sender, status)

    def _handle_message(self, message: Message) -> None:
        if message.message_type != MessageType.SIGNAL:
            return
        if (
            message.interface == "org.freedesktop.DBus"
            and message.member == "NameOwnerChanged"
        ):
            self._handle_name_owner_changed(message)
            return
        if (
            message.interface == self.PROPERTIES_INTERFACE
            and message.member == "PropertiesChanged"
        ):
            self._handle_properties_changed(message)

    async def _load_playback_status(
        self, monitor_bus: MessageBus, name: str, owner: str
    ) -> None:
        try:
            reply = await monitor_bus.call(
                Message(
                    destination=name,
                    path="/org/mpris/MediaPlayer2",
                    interface=self.PROPERTIES_INTERFACE,
                    member="Get",
                    signature="ss",
                    body=[self.PLAYER_INTERFACE, "PlaybackStatus"],
                )
            )
        except Exception as error:
            self._log(
                f'[mpris] initial playback query failed name={name} '
                f'owner={owner} error={error}'
            )
            return
        if reply.message_type == MessageType.ERROR or not reply.body:
            self._log(
                f'[mpris] initial playback unavailable name={name} owner={owner}'
            )
            return
        if self._statuses.get(owner) != "Unknown":
            return
        status = str(self._variant_value(reply.body[0]))
        self._statuses[owner] = status
        self._log(
            f'[mpris] initial playback name={name} owner={owner} status={status}'
        )
        if self._on_event is not None:
            self._on_event("playback", name, owner, status)

    async def _load_existing_players(self, monitor_bus: MessageBus) -> None:
        list_reply = await monitor_bus.call(
            Message(
                destination="org.freedesktop.DBus",
                path="/org/freedesktop/DBus",
                interface="org.freedesktop.DBus",
                member="ListNames",
            )
        )
        if list_reply.message_type == MessageType.ERROR or not list_reply.body:
            return

        for name in list_reply.body[0]:
            if not name.startswith(self.PLAYER_PREFIX):
                continue
            owner_reply = await monitor_bus.call(
                Message(
                    destination="org.freedesktop.DBus",
                    path="/org/freedesktop/DBus",
                    interface="org.freedesktop.DBus",
                    member="GetNameOwner",
                    signature="s",
                    body=[name],
                )
            )
            if owner_reply.message_type != MessageType.ERROR and owner_reply.body:
                owner = owner_reply.body[0]
                self._owners[owner] = name
                self._statuses[owner] = "Unknown"
                self._log(f'[mpris] existing player name={name} owner={owner}')

                if self._on_event is not None:
                    self._on_event("appeared", name, owner)
                await self._load_playback_status(monitor_bus, name, owner)

    async def start(self) -> None:
        if self._bus is not None:
            return

        monitor_bus = await MessageBus().connect()
        await self._load_existing_players(monitor_bus)
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
                        "type='signal',interface='org.freedesktop.DBus',member='NameOwnerChanged',arg0namespace='org.mpris.MediaPlayer2'",
                        "type='signal',interface='org.freedesktop.DBus.Properties',member='PropertiesChanged',path='/org/mpris/MediaPlayer2'",
                    ],
                    0,
                ],
            )
        )
        if reply.message_type == MessageType.ERROR:
            monitor_bus.disconnect()
            raise RuntimeError(f'Unable to monitor MPRIS: {reply.body}')

        self._bus = monitor_bus
        self._log('[mpris] monitor started')

    def snapshot(self) -> List[Dict[str, str]]:
        return [
            {
                "name": name,
                "owner": owner,
                "status": self._statuses.get(owner, "Unknown"),
            }
            for owner, name in self._owners.items()
        ]

    async def stop(self) -> None:
        if self._bus is None:
            return
        self._bus.disconnect()
        self._bus = None
        self._owners.clear()
        self._statuses.clear()
        self._log('[mpris] monitor stopped')