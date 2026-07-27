from typing import Any, Dict, Iterable, List, Tuple

from .base import AppPolicy
from .firefox import FirefoxPolicy
from .plex import PlexPolicy


class PolicyRegistry:
    def __init__(self):
        self._policies: List[AppPolicy] = [PlexPolicy(), FirefoxPolicy()]

    def _dispatch(self, method: str, *args: Any) -> bool:
        changed = False
        for policy in self._policies:
            changed = getattr(policy, method)(*args) or changed
        return changed

    def on_portal_inhibit(self, sender: str, application: str, reason: str) -> bool:
        return self._dispatch("on_portal_inhibit", sender, application, reason)

    def on_portal_close(self, sender: str, path: str) -> bool:
        return self._dispatch("on_portal_close", sender, path)

    def on_mpris_player_appeared(self, name: str, owner: str) -> bool:
        return self._dispatch("on_mpris_player_appeared", name, owner)

    def on_mpris_player_disappeared(self, name: str, owner: str) -> bool:
        return self._dispatch("on_mpris_player_disappeared", name, owner)

    def on_mpris_playback(self, name: str, owner: str, status: str) -> bool:
        return self._dispatch("on_mpris_playback", name, owner, status)

    def evaluate(self, requests: Iterable[Any]) -> Tuple[bool, float, str]:
        active_requests = list(requests)
        for policy in self._policies:
            policy.on_requests_changed(active_requests)

        policy_for_request: Dict[int, AppPolicy] = {}
        for request in active_requests:
            for policy in self._policies:
                if policy.handles(request):
                    policy_for_request[request.cookie] = policy
                    break

        generic_active = any(
            request.cookie not in policy_for_request for request in active_requests
        )
        if generic_active:
            return True, 0.0, "default"

        for policy in self._policies:
            if policy.is_inhibited(active_requests):
                return True, 0.0, policy.name

        grace_seconds = max(
            (policy.uninhibit_grace_seconds(active_requests) for policy in self._policies),
            default=0.0,
        )
        return False, grace_seconds, "none"

    def reset(self) -> None:
        for policy in self._policies:
            policy.reset()