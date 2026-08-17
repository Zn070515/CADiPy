"""Serialized ownership of a CAD backend executor."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from enum import Enum
from typing import Any, TypeVar

from cadipy.domain.errors import SessionClosedError, WorkerError


class HostState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


ResultT = TypeVar("ResultT")
Command = tuple[Callable[[], Any], Future[Any]]


class StaExecutorHost:
    """Run one backend executor and its commands on one dedicated thread."""

    def __init__(
        self,
        executor_factory: Callable[[], Any],
        command_timeout: float | None = None,
    ) -> None:
        self._executor_factory = executor_factory
        self._command_timeout = command_timeout
        self._commands: queue.Queue[Command | None] = queue.Queue()
        self._state = HostState.CREATED
        self._state_lock = threading.Lock()
        self._started = threading.Event()
        self._startup_error: BaseException | None = None
        self._worker_ident: int | None = None
        self._worker = threading.Thread(target=self._run, name="cadipy-executor", daemon=True)

    @property
    def state(self) -> HostState:
        with self._state_lock:
            return self._state

    def start(self) -> None:
        with self._state_lock:
            if self._state is HostState.RUNNING:
                return
            if self._state is not HostState.CREATED:
                raise SessionClosedError("executor host cannot be started in its current state")
            self._worker.start()
        self._started.wait()
        if self._startup_error is not None:
            raise self._startup_error

    def submit(self, command: Callable[[], ResultT], timeout: float | None = None) -> ResultT:
        if threading.get_ident() == self._worker_ident:
            self._ensure_accepting()
            return command()

        future: Future[ResultT] = Future()
        with self._state_lock:
            self._ensure_accepting_locked()
            self._commands.put((command, future))

        wait_timeout = self._command_timeout if timeout is None else timeout
        try:
            return future.result(timeout=wait_timeout)
        except TimeoutError:
            self._fail_after_timeout()
            raise

    def close(self, timeout: float = 30.0) -> None:
        with self._state_lock:
            if self._state is HostState.CLOSED:
                return
            if self._state is HostState.CREATED:
                self._state = HostState.CLOSED
                return
            if self._state is HostState.CLOSING:
                worker = self._worker
            else:
                worker = self._worker
                self._state = self._state if self._state is HostState.FAILED else HostState.CLOSING
                self._commands.put(None)
        worker.join(timeout)
        if worker.is_alive():
            with self._state_lock:
                self._state = HostState.FAILED
            raise TimeoutError("executor host did not close before the timeout")

    def _run(self) -> None:
        self._worker_ident = threading.get_ident()
        executor: Any = None
        try:
            executor = self._executor_factory()
            with self._state_lock:
                self._state = HostState.RUNNING
        except BaseException as exc:
            self._startup_error = exc
            with self._state_lock:
                self._state = HostState.FAILED
        finally:
            self._started.set()

        if executor is None:
            return

        while True:
            item = self._commands.get()
            if item is None:
                try:
                    disconnect = getattr(executor, "disconnect", None)
                    if callable(disconnect):
                        disconnect()
                except BaseException as exc:
                    with self._state_lock:
                        self._state = HostState.FAILED
                    self._startup_error = exc
                else:
                    with self._state_lock:
                        if self._state is not HostState.FAILED:
                            self._state = HostState.CLOSED
                return

            command, future = item
            if self.state is HostState.FAILED:
                if not future.done():
                    future.set_exception(WorkerError("executor host failed"))
                continue
            try:
                future.set_result(command())
            except BaseException as exc:
                if not future.done():
                    future.set_exception(exc)

    def _ensure_accepting(self) -> None:
        with self._state_lock:
            self._ensure_accepting_locked()

    def _ensure_accepting_locked(self) -> None:
        if self._state is HostState.CLOSED or self._state is HostState.CLOSING:
            raise SessionClosedError("executor host is closed")
        if self._state is not HostState.RUNNING:
            raise WorkerError("executor host is not running")

    def _fail_after_timeout(self) -> None:
        with self._state_lock:
            if self._state is HostState.RUNNING:
                self._state = HostState.FAILED
