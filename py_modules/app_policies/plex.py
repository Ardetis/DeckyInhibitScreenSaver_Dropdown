from typing import Any, Iterable, List

from .base import AppPolicy


class PlexPolicy(AppPolicy):
    name = "plex"
    PAUSE_GRACE_SECONDS = 3.0

    def __init__(self):
        self._audio_seen = False

    @staticmethod
    def _is_session_request(request: Any) -> bool:
        return request.application == "PlexHTPC" and request.reason.lower() == "playing"

    @staticmethod
    def _is_audio_request(request: Any) -> bool:
        return "plex-bin" in request.application and request.reason.lower() == "playing audio"

    def handles(self, request: Any) -> bool:
        return self._is_session_request(request) or self._is_audio_request(request)

    def _plex_requests(self, requests: Iterable[Any]) -> List[Any]:
        return [request for request in requests if self.handles(request)]

    def on_requests_changed(self, requests: Iterable[Any]) -> None:
        plex_requests = self._plex_requests(requests)
        if any(self._is_audio_request(request) for request in plex_requests):
            self._audio_seen = True
        if not plex_requests:
            self.reset()

    def is_inhibited(self, requests: Iterable[Any]) -> bool:
        plex_requests = self._plex_requests(requests)
        audio_active = any(self._is_audio_request(request) for request in plex_requests)
        session_active = any(self._is_session_request(request) for request in plex_requests)

        if audio_active:
            return True
        if session_active:
            # Before an audio request is observed, preserve Plex's normal inhibitor behavior.
            return not self._audio_seen
        return False

    def uninhibit_grace_seconds(self, requests: Iterable[Any]) -> float:
        plex_requests = self._plex_requests(requests)
        audio_active = any(self._is_audio_request(request) for request in plex_requests)
        session_active = any(self._is_session_request(request) for request in plex_requests)
        if self._audio_seen and session_active and not audio_active:
            return self.PAUSE_GRACE_SECONDS
        return 0.0

    def reset(self) -> None:
        self._audio_seen = False