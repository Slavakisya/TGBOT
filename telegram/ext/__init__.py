"""Minimal :mod:`telegram.ext` stubs used for tests."""

from __future__ import annotations

from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any, Callable, Dict, Iterable, List, Optional


class Filter:
    def __init__(self, name: str) -> None:
        self.name = name

    def __and__(self, other: "Filter") -> "Filter":
        return Filter(f"({self.name}&{other.name})")

    def __or__(self, other: "Filter") -> "Filter":
        return Filter(f"({self.name}|{other.name})")

    def __invert__(self) -> "Filter":
        return Filter(f"~{self.name}")


class _FiltersNamespace:
    def __init__(self) -> None:
        self.TEXT = Filter("TEXT")
        self.COMMAND = Filter("COMMAND")

    def Regex(self, pattern: str) -> Filter:  # noqa: N802 - mimic PTB API
        return Filter(f"Regex({pattern})")


filters = _FiltersNamespace()


class ContextTypes:
    DEFAULT_TYPE = object


@dataclass
class CommandHandler:
    command: str
    callback: Callable[..., Any]


@dataclass
class MessageHandler:
    filter: Filter
    callback: Callable[..., Any]
    block: bool = True


@dataclass
class CallbackQueryHandler:
    callback: Callable[..., Any]
    pattern: str | None = None


@dataclass
class ChatMemberHandler:
    callback: Callable[..., Any]
    member_status: str

    MY_CHAT_MEMBER: str = "my_chat_member"


class ConversationHandler:
    END = -1

    def __init__(
        self,
        entry_points: Iterable[Any],
        states: Dict[Any, Iterable[Any]],
        fallbacks: Iterable[Any],
    ) -> None:
        self.entry_points = list(entry_points)
        self.states = {k: list(v) for k, v in states.items()}
        self.fallbacks = list(fallbacks)


class Job:
    def __init__(self, callback: Callable[..., Any], name: str | None, data: dict | None) -> None:
        self.callback = callback
        self.name = name
        self.data = data or {}
        self._removed = False

    def schedule_removal(self) -> None:
        self._removed = True


class JobQueue:
    def __init__(self) -> None:
        self._jobs: List[Job] = []
        self.application: "Application" | None = None

    def set_application(self, app: "Application") -> None:
        self.application = app

    def run_daily(self, callback: Callable[..., Any], time=None, name: str | None = None, data: Optional[dict] = None) -> Job:
        job = Job(callback, name, data)
        self._jobs.append(job)
        return job

    def jobs(self) -> List[Job]:
        return list(self._jobs)


class _ApplicationBuilder:
    def __init__(self, app_cls: type["Application"]) -> None:
        self._app_cls = app_cls
        self._token: str | None = None
        self._job_queue: JobQueue | None = None
        self._post_init: Callable[["Application"], Any] | None = None
        self._post_shutdown: Callable[["Application"], Any] | None = None

    def token(self, token: str) -> "_ApplicationBuilder":
        self._token = token
        return self

    def job_queue(self, job_queue: JobQueue) -> "_ApplicationBuilder":
        self._job_queue = job_queue
        return self

    def post_init(self, callback: Callable[["Application"], Any]) -> "_ApplicationBuilder":
        self._post_init = callback
        return self

    def post_shutdown(self, callback: Callable[["Application"], Any]) -> "_ApplicationBuilder":
        self._post_shutdown = callback
        return self

    def build(self) -> "Application":
        app = self._app_cls(
            token=self._token,
            job_queue=self._job_queue,
            post_init=self._post_init,
            post_shutdown=self._post_shutdown,
        )
        if app.job_queue is not None:
            app.job_queue.set_application(app)
        return app


async def _async_noop(*args, **kwargs):
    return None


async def _async_get_me(*args, **kwargs):
    return SimpleNamespace(username="stub", id=0)


class Application:
    def __init__(
        self,
        token: str | None,
        job_queue: JobQueue | None,
        post_init: Callable[["Application"], Any] | None,
        post_shutdown: Callable[["Application"], Any] | None,
    ) -> None:
        self._token = token
        self.job_queue = job_queue
        self._post_init = post_init
        self._post_shutdown = post_shutdown
        self.handlers: List[tuple[Any, int]] = []
        self.bot = SimpleNamespace(
            delete_webhook=_async_noop,
            get_me=_async_get_me,
            send_message=_async_noop,
        )

    @classmethod
    def builder(cls) -> _ApplicationBuilder:
        return _ApplicationBuilder(cls)

    def add_handler(self, handler: Any, group: int = 0) -> None:
        self.handlers.append((handler, group))

    async def bot_get_me(self):
        return SimpleNamespace(username="stub", id=0)

    def run_polling(self, close_loop: bool = False) -> None:
        pass


def _noop(*args, **kwargs):
    return None


ApplicationBuilder = _ApplicationBuilder


__all__ = [
    "Application",
    "CommandHandler",
    "MessageHandler",
    "CallbackQueryHandler",
    "ChatMemberHandler",
    "ConversationHandler",
    "JobQueue",
    "ContextTypes",
    "filters",
]
