import asyncio
import json
import logging
from urllib.parse import quote
from typing import Literal

import requests
from pywebpush import webpush, WebPushException

from composition.application.ports.outbound.completion_push_port import CompletionPushCommand

logger = logging.getLogger(__name__)


class NoRedirectSession(requests.Session):
    def post(self, url, **kwargs):
        return super().post(url, allow_redirects=False, **kwargs)


class WebPushAdapter:
    def __init__(self, private_key: str, subject: str):
        self._private_key = private_key
        self._subject = subject

    async def send(self, command: CompletionPushCommand) -> Literal["accepted", "retry", "invalid"]:
        return await asyncio.to_thread(self._send, command)

    def _send(self, command: CompletionPushCommand) -> Literal["accepted", "retry", "invalid"]:
        payload = json.dumps({"job_id": command.job_id,
            "url": "/my-assets?job=" + quote(command.job_id, safe="") + "&from=notification"})
        try:
            with NoRedirectSession() as session:
                response = webpush(
                    subscription_info={"endpoint": command.endpoint, "keys": {"p256dh": command.p256dh, "auth": command.auth}},
                    data=payload, vapid_private_key=self._private_key,
                    vapid_claims={"sub": self._subject}, ttl=3600,
                    timeout=10, requests_session=session,
                    headers={"Urgency": "normal"},
                )
            return "accepted" if 200 <= response.status_code < 300 else "invalid"
        except WebPushException as exc:
            status = exc.response.status_code if exc.response is not None else 0
            logger.warning("completion_push_rejected status=%s job_id=%s", status, command.job_id)
            return "invalid" if status in (400, 404, 410, 413) else "retry"
        except requests.RequestException:
            logger.warning("completion_push_network_error job_id=%s", command.job_id)
            return "retry"
