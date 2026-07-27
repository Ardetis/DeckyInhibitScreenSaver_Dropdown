from typing import Any, Dict, Iterable, Set

from .base import AppPolicy


class FirefoxPolicy(AppPolicy):
    name = "firefox"
    PAUSE_GRACE_SECONDS = 3.0
    APPLICATION = "org.mozilla.firefox"
    PLAYER_PREFIX = "org.mpris.MediaPlayer2.firefox"

    def __init__(self):
        self._portal_owners: Set[str] = set()
        self._players: Dict[str, str] = {}

    def handles(self, request: Any) -> bool:
        return False

    def on_portal_inhibit(self, sender: str, application: str, reason: str) -> bool:
        if application != self.APPLICATION:
            return False
        before = self.is_inhibited([])
        self._portal_owners.add(sender)
        return before != self.is_inhibited([])

    def on_portal_close(self, sender: str, path: str) -> bool:
        if sender not in self._portal_owners:
            return False
        before = self.is_inhibited([])
        self._portal_owners.discard(sender)
        self._players.pop(sender, None)
        return before != self.is_inhibited([])

    def on_mpris_player_appeared(self, name: str, owner: str) -> bool:
        if not name.startswith(self.PLAYER_PREFIX):
            return False
        before = self.is_inhibited([])
        self._players[owner] = "Unknown"
        return before != self.is_inhibited([])

    def on_mpris_player_disappeared(self, name: str, owner: str) -> bool:
        if not name.startswith(self.PLAYER_PREFIX):
            return False
        before = self.is_inhibited([])
        self._players[owner] = "Stopped"
        return before != self.is_inhibited([])

    def on_mpris_playback(self, name: str, owner: str, status: str) -> bool:
        if not name.startswith(self.PLAYER_PREFIX):
            return False
        before = self.is_inhibited([])
        self._players[owner] = status
        return before != self.is_inhibited([])

    def is_inhibited(self, requests: Iterable[Any]) -> bool:
        for owner in self._portal_owners:
            if self._players.get(owner, "Unknown") in ("Unknown", "Playing"):
                return True
        return False

    def uninhibit_grace_seconds(self, requests: Iterable[Any]) -> float:
        if not self._portal_owners:
            return 0.0
        if any(
            self._players.get(owner) in ("Paused", "Stopped")
            for owner in self._portal_owners
        ):
            return self.PAUSE_GRACE_SECONDS
        return 0.0

    def reset(self) -> None:
        self._portal_owners.clear()
