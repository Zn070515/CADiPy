"""Serialized ownership of a CAD backend executor."""

from __future__ import annotations

import queue
import threading
from collections.abc import Callable
from concurrent.futures import Future
from enum import Enum
from typing import Any, Protocol, TypeVar, runtime_checkable

from cadipy.domain.errors import SessionClosedError, WorkerError


class HostState(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    CLOSING = "closing"
    CLOSED = "closed"
    FAILED = "failed"


ResultT = TypeVar("ResultT")
Command = tuple[Callable[[], Any], Future[Any]]
ApartmentHook = Callable[[], None]


@runtime_checkable
class ExecutorHost(Protocol):
    """Contract for serialized executor lifecycle ownership."""

    def start(self) -> None: ...

    def submit(self, command: Callable[[], ResultT], timeout: float | None = None) -> ResultT: ...

    def close(self, timeout: float = 30.0) -> None: ...


class StaExecutorHost(ExecutorHost):
    """Run one backend executor and its commands on one dedicated thread."""

    def __init__(
        self,
        executor_factory: Callable[[], Any],
        command_timeout: float | None = None,
        *,
        apartment_init: ApartmentHook | None = None,
        apartment_uninit: ApartmentHook | None = None,
    ) -> None:
        self._executor_factory = executor_factory
        self._command_timeout = command_timeout
        self._apartment_init = apartment_init or _noop_apartment_hook
        self._apartment_uninit = apartment_uninit or _noop_apartment_hook
        self._commands: queue.Queue[Command | None] = queue.Queue()
        self._state = HostState.CREATED
        self._state_lock = threading.Lock()
        self._started = threading.Event()
        self._startup_error: BaseException | None = None
        self._cleanup_error: WorkerError | None = None
        self._worker_ident: int | None = None
        self._worker_started = False
        self._stop_enqueued = False
        self._worker = threading.Thread(target=self._run, name="cadipy-executor", daemon=True)

    @property
    def state(self) -> HostState:
        with self._state_lock:
            return self._state

    def start(self) -> None:
        with self._state_lock:
            if self._state is HostState.RUNNING:
                pass
            elif self._state is HostState.CREATED:
                self._state = HostState.RUNNING
                try:
                    self._worker.start()
                except BaseException as exc:
                    error = WorkerError("executor host startup failed")
                    self._startup_error = error
                    self._state = HostState.FAILED
                    self._started.set()
                    raise error from exc
                self._worker_started = True
            else:
                raise SessionClosedError("executor host cannot be started in its current state")
        self._started.wait()
        if self._cleanup_error is not None:
            raise self._cleanup_error
        if self._startup_error is not None:
            raise self._startup_error

    def submit(self, command: Callable[[], ResultT], timeout: float | None = None) -> ResultT:
        if threading.get_ident() == self._worker_ident:
            nested_future: Future[ResultT] = Future()
            with self._state_lock:
                self._ensure_accepting_locked()
                self._commands.put((command, nested_future))
            self._run_until_complete(nested_future)
            return nested_future.result()

        future: Future[ResultT] = Future()
        with self._state_lock:
            self._ensure_accepting_locked()
            self._commands.put((command, future))

        wait_timeout = self._command_timeout if timeout is None else timeout
        try:
            return future.result(timeout=wait_timeout)
        except TimeoutError as exc:
            self._fail_after_timeout(exc)
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
            if not self._stop_enqueued and worker.is_alive():
                self._commands.put(None)
                self._stop_enqueued = True
            if not self._worker_started:
                return
        worker.join(timeout)
        if worker.is_alive():
            with self._state_lock:
                self._state = HostState.FAILED
            raise TimeoutError("executor host did not close before the timeout")
        if self._cleanup_error is not None:
            raise self._cleanup_error

    def _run(self) -> None:
        self._worker_ident = threading.get_ident()
        executor: Any = None
        apartment_initialized = False
        try:
            self._apartment_init()
            apartment_initialized = True
            executor = self._executor_factory()
        except BaseException as exc:
            self._startup_error = exc
            with self._state_lock:
                self._state = HostState.FAILED

        if executor is None:
            if self._startup_error is None:
                self._startup_error = RuntimeError("executor factory returned no executor")
                with self._state_lock:
                    self._state = HostState.FAILED
            if apartment_initialized:
                self._uninitialize_apartment()
            if self._cleanup_error is None:
                self._record_startup_failure(self._startup_error)
            failure = self._cleanup_error or self._startup_error
            assert isinstance(failure, WorkerError)
            self._reject_pending(failure)
            self._started.set()
            return

        self._started.set()
        try:
            self._serve()
        except BaseException as exc:
            self._record_worker_failure(exc)
        finally:
            self._disconnect_and_uninitialize(executor)

    def _serve(self) -> None:
        while True:
            item = self._commands.get()
            if item is None:
                return
            self._execute(item)

    def _run_until_complete(self, target: Future[Any]) -> None:
        while not target.done():
            item = self._commands.get()
            if item is None:
                target.set_exception(SessionClosedError("executor host is closed"))
                self._commands.put(None)
                return
            self._execute(item)

    def _execute(self, item: Command) -> None:
        command, future = item
        if self.state is HostState.FAILED:
            if not future.done():
                future.set_exception(WorkerError("executor host failed"))
            return
        try:
            future.set_result(command())
        except BaseException as exc:
            if not future.done():
                future.set_exception(exc)

    def _disconnect_and_uninitialize(self, executor: Any) -> None:
        cleanup_cause: BaseException | None = None
        try:
            disconnect = getattr(executor, "disconnect", None)
            if callable(disconnect):
                disconnect()
        except BaseException as exc:
            cleanup_cause = exc
        try:
            self._apartment_uninit()
        except BaseException as exc:
            cleanup_cause = cleanup_cause or exc
        if cleanup_cause is not None:
            self._record_cleanup_failure(cleanup_cause)
        else:
            with self._state_lock:
                if self._state is not HostState.FAILED:
                    self._state = HostState.CLOSED

    def _uninitialize_apartment(self) -> None:
        try:
            self._apartment_uninit()
        except BaseException as exc:
            self._record_cleanup_failure(exc)

    def _record_cleanup_failure(self, cause: BaseException) -> None:
        error = WorkerError("executor host cleanup failed")
        error.__cause__ = cause
        with self._state_lock:
            self._cleanup_error = error
            self._state = HostState.FAILED

    def _record_worker_failure(self, cause: BaseException) -> None:
        error = WorkerError("executor host worker failed")
        error.__cause__ = cause
        with self._state_lock:
            self._state = HostState.FAILED
        self._reject_pending(error)

    def _reject_pending(self, error: WorkerError) -> None:
        while True:
            try:
                item = self._commands.get_nowait()
            except queue.Empty:
                return
            if item is not None:
                _, future = item
                if not future.done():
                    future.set_exception(error)

    def _record_startup_failure(self, cause: BaseException) -> None:
        error = WorkerError("executor host startup failed")
        error.__cause__ = cause
        with self._state_lock:
            self._startup_error = error
            self._state = HostState.FAILED

    def _ensure_accepting(self) -> None:
        with self._state_lock:
            self._ensure_accepting_locked()

    def _ensure_accepting_locked(self) -> None:
        if self._state is HostState.CLOSED or self._state is HostState.CLOSING:
            raise SessionClosedError("executor host is closed")
        if self._state is not HostState.RUNNING:
            raise WorkerError("executor host is not running")

    def _fail_after_timeout(self, cause: BaseException) -> None:
        error = WorkerError("executor host command timed out")
        error.__cause__ = cause
        with self._state_lock:
            if self._state is not HostState.RUNNING:
                return
            self._state = HostState.FAILED
        self._reject_pending(error)


def _noop_apartment_hook() -> None:
    return None
