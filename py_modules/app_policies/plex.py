from typing import Any, Iterable

from .base import AppPolicy


class PlexPolicy(AppPolicy):
    name = "plex"

    @staticmethod
    def _is_session_request(request: Any) -> bool:
        return request.application == "PlexHTPC" and request.reason.lower() == "playing"

    @staticmethod
    def _is_audio_request(request: Any) -> bool:
        return "plex-bin" in request.application and request.reason.lower() == "playing audio"

    def handles(self, request: Any) -> bool:
        return self._is_session_request(request) or self._is_audio_request(request)

    def is_inhibited(self, requests: Iterable[Any]) -> bool:
        return any(self.handles(request) for request in requests)
