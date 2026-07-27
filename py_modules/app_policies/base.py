from typing import Any, Iterable


class AppPolicy:
    name = "base"

    def handles(self, request: Any) -> bool:
        raise NotImplementedError

    def on_requests_changed(self, requests: Iterable[Any]) -> None:
        pass

    def is_inhibited(self, requests: Iterable[Any]) -> bool:
        raise NotImplementedError

    def uninhibit_grace_seconds(self, requests: Iterable[Any]) -> float:
        return 0.0

    def reset(self) -> None:
        pass
    def on_portal_inhibit(self, sender: str, application: str, reason: str) -> bool:
        return False

    def on_portal_close(self, sender: str, path: str) -> bool:
        return False

    def on_mpris_player_appeared(self, name: str, owner: str) -> bool:
        return False

    def on_mpris_player_disappeared(self, name: str, owner: str) -> bool:
        return False

    def on_mpris_playback(self, name: str, owner: str, status: str) -> bool:
        return False
