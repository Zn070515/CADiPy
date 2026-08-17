from __future__ import annotations

import threading
import time
from collections import deque
from concurrent.futures import Future

import pytest

from cadipy.domain.errors import SessionClosedError, WorkerError
from cadipy.runtime.host import HostState, StaExecutorHost


class RecordingExecutor:
    def __init__(self, events: list[str] | None = None) -> None:
        self.events = events if events is not None else []
        self.events.append("created")

    def disconnect(self) -> None:
        self.events.append("disconnected")


def test_host_serializes_commands_on_one_worker_thread() -> None:
    host = StaExecutorHost(lambda: RecordingExecutor())
    host.start()
    try:
        thread_ids = [host.submit(lambda: threading.get_ident()) for _ in range(3)]
        assert len(set(thread_ids)) == 1
    finally:
        host.close(timeout=30.0)


def test_host_constructs_executor_on_its_worker_thread() -> None:
    factory_thread: list[int] = []

    def factory() -> RecordingExecutor:
        factory_thread.append(threading.get_ident())
        return RecordingExecutor()

    host = StaExecutorHost(factory)
    host.start()
    try:
        command_thread = host.submit(threading.get_ident)
        assert factory_thread == [command_thread]
    finally:
        host.close(timeout=30.0)


def test_host_pairs_apartment_hooks_on_worker_thread() -> None:
    calls: list[tuple[str, int]] = []

    def apartment_init() -> None:
        calls.append(("init", threading.get_ident()))

    def apartment_uninit() -> None:
        calls.append(("uninit", threading.get_ident()))

    def factory() -> RecordingExecutor:
        calls.append(("factory", threading.get_ident()))
        return RecordingExecutor()

    host = StaExecutorHost(
        factory,
        apartment_init=apartment_init,
        apartment_uninit=apartment_uninit,
    )
    host.start()
    try:
        command_thread = host.submit(threading.get_ident)
    finally:
        host.close(timeout=30.0)

    assert calls == [
        ("init", command_thread),
        ("factory", command_thread),
        ("uninit", command_thread),
    ]


def test_host_concurrent_start_calls_start_worker_once() -> None:
    host = StaExecutorHost(
        lambda: RecordingExecutor(), apartment_init=lambda: None, apartment_uninit=lambda: None
    )
    barrier = threading.Barrier(3)
    errors: list[BaseException] = []

    def start() -> None:
        barrier.wait()
        try:
            host.start()
        except BaseException as exc:
            errors.append(exc)

    threads = [threading.Thread(target=start) for _ in range(2)]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join(timeout=1.0)

    try:
        assert not errors
        assert host.submit(lambda: "running") == "running"
    finally:
        host.close(timeout=30.0)


def test_host_surfaces_disconnect_failure_and_preserves_failed_state() -> None:
    cleanup_error = RuntimeError("disconnect failed")

    class FailingExecutor(RecordingExecutor):
        def disconnect(self) -> None:
            raise cleanup_error

    uninitialized = threading.Event()
    host = StaExecutorHost(
        lambda: FailingExecutor(),
        apartment_init=lambda: None,
        apartment_uninit=uninitialized.set,
    )
    host.start()

    with pytest.raises(WorkerError, match="cleanup failed") as exc_info:
        host.close(timeout=30.0)

    assert host.state is HostState.FAILED
    assert exc_info.value.__cause__ is cleanup_error
    assert uninitialized.is_set()


def test_host_close_waits_for_thread_start_before_joining(monkeypatch: pytest.MonkeyPatch) -> None:
    original_start = threading.Thread.start
    start_entered = threading.Event()
    release_start = threading.Event()
    errors: list[BaseException] = []
    host = StaExecutorHost(
        lambda: RecordingExecutor(),
        apartment_init=lambda: None,
        apartment_uninit=lambda: None,
    )

    def delayed_start(thread: threading.Thread) -> None:
        if thread is not host._worker:
            original_start(thread)
            return
        start_entered.set()
        release_start.wait(timeout=1.0)
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", delayed_start)

    def start_host() -> None:
        try:
            host.start()
        except BaseException as exc:
            errors.append(exc)

    start_thread = threading.Thread(target=start_host)
    start_thread.start()
    assert start_entered.wait(timeout=1.0)

    close_thread = threading.Thread(target=lambda: host.close(timeout=1.0))
    close_thread.start()
    release_start.set()
    start_thread.join(timeout=1.0)
    close_thread.join(timeout=1.0)

    assert not errors
    assert not start_thread.is_alive()
    assert not close_thread.is_alive()
    assert host.state is HostState.CLOSED


def test_host_reentrant_submission_preserves_existing_fifo_work() -> None:
    events: list[str] = []
    host = StaExecutorHost(
        lambda: RecordingExecutor(),
        apartment_init=lambda: None,
        apartment_uninit=lambda: None,
    )
    host.start()
    outer_future: Future[str] = Future()
    queued_future: Future[str] = Future()

    def queued_command() -> str:
        events.append("queued")
        return "queued"

    def outer_command() -> str:
        events.append("outer")
        return host.submit(lambda: events.append("nested") or "nested")

    host._commands.put((outer_command, outer_future))
    host._commands.put((queued_command, queued_future))

    try:
        assert outer_future.result(timeout=1.0) == "nested"
        assert events == ["outer", "queued", "nested"]
        assert queued_future.result() == "queued"
    finally:
        host.close(timeout=30.0)


def test_host_surfaces_apartment_cleanup_failure_during_failed_start() -> None:
    startup_error = RuntimeError("factory failed")
    cleanup_error = RuntimeError("uninitialize failed")

    def factory() -> RecordingExecutor:
        raise startup_error

    def uninitialize() -> None:
        raise cleanup_error

    host = StaExecutorHost(
        factory,
        apartment_init=lambda: None,
        apartment_uninit=uninitialize,
    )

    with pytest.raises(WorkerError, match="cleanup failed") as exc_info:
        host.start()

    assert host.state is HostState.FAILED
    assert exc_info.value.__cause__ is cleanup_error


def test_host_start_waits_for_failed_start_cleanup_before_reporting_error() -> None:
    startup_error = RuntimeError("factory failed")
    cleanup_started = threading.Event()
    release_cleanup = threading.Event()
    errors: list[BaseException] = []
    host = StaExecutorHost(
        lambda: (_ for _ in ()).throw(startup_error),
        apartment_init=lambda: None,
        apartment_uninit=lambda: (cleanup_started.set(), release_cleanup.wait(timeout=1.0)),
    )

    def start_host() -> None:
        try:
            host.start()
        except BaseException as exc:
            errors.append(exc)

    start_thread = threading.Thread(target=start_host)
    start_thread.start()
    assert cleanup_started.wait(timeout=1.0)
    assert start_thread.is_alive()
    assert not errors

    release_cleanup.set()
    start_thread.join(timeout=1.0)

    assert len(errors) == 1
    assert isinstance(errors[0], WorkerError)
    assert errors[0].__cause__ is startup_error
    assert host.state is HostState.FAILED


def test_host_rejects_none_executor_as_failed_start() -> None:
    uninitialized = threading.Event()
    host = StaExecutorHost(
        lambda: None,
        apartment_init=lambda: None,
        apartment_uninit=uninitialized.set,
    )

    with pytest.raises(WorkerError, match="startup failed") as exc_info:
        host.start()

    assert host.state is HostState.FAILED
    assert not host._worker.is_alive()
    assert uninitialized.is_set()
    assert isinstance(exc_info.value.__cause__, RuntimeError)


def test_host_rejects_commands_after_close() -> None:
    host = StaExecutorHost(lambda: RecordingExecutor())
    host.start()
    host.close(timeout=30.0)
    with pytest.raises(SessionClosedError):
        host.submit(lambda: None)


def test_host_runs_commands_fifo_and_disconnects_after_accepted_work() -> None:
    events: list[str] = []
    host = StaExecutorHost(lambda: RecordingExecutor(events))
    host.start()
    try:
        assert [
            host.submit(lambda value=value: events.append(str(value)) or value)
            for value in range(3)
        ] == [0, 1, 2]
    finally:
        host.close(timeout=30.0)

    assert events == ["created", "0", "1", "2", "disconnected"]
    assert host.state is HostState.CLOSED


def test_host_delivers_command_exceptions_without_stopping_worker() -> None:
    host = StaExecutorHost(lambda: RecordingExecutor())
    host.start()
    try:
        with pytest.raises(ValueError, match="command failed"):
            host.submit(lambda: (_ for _ in ()).throw(ValueError("command failed")))
        assert host.submit(lambda: "still running") == "still running"
    finally:
        host.close(timeout=30.0)


def test_host_transitions_to_failed_when_executor_creation_fails() -> None:
    host = StaExecutorHost(lambda: (_ for _ in ()).throw(RuntimeError("cannot create")))
    with pytest.raises(WorkerError, match="startup failed") as exc_info:
        host.start()

    assert host.state is HostState.FAILED
    assert isinstance(exc_info.value.__cause__, RuntimeError)
    with pytest.raises(WorkerError):
        host.submit(lambda: None)


def test_host_timeout_does_not_interrupt_running_command() -> None:
    started = threading.Event()
    release = threading.Event()
    finished = threading.Event()

    def command() -> str:
        started.set()
        release.wait(timeout=30.0)
        finished.set()
        return "done"

    host = StaExecutorHost(lambda: RecordingExecutor(), command_timeout=0.01)
    host.start()
    try:
        with pytest.raises(TimeoutError):
            host.submit(command)
        assert host.state is HostState.FAILED
        with pytest.raises(WorkerError):
            host.submit(lambda: None)
        release.set()
        assert finished.wait(timeout=1.0)
    finally:
        host.close(timeout=30.0)


def test_host_rejects_queued_commands_after_timeout() -> None:
    started = threading.Event()
    release = threading.Event()
    calls: deque[str] = deque()
    errors: list[BaseException] = []

    def blocking() -> None:
        started.set()
        release.wait(timeout=30.0)

    host = StaExecutorHost(lambda: RecordingExecutor())
    host.start()
    try:

        def submit_blocking() -> None:
            try:
                host.submit(blocking)
            except BaseException as exc:
                errors.append(exc)

        first = threading.Thread(target=submit_blocking)
        first.start()
        assert started.wait(timeout=1.0)
        with pytest.raises(TimeoutError):
            host.submit(lambda: calls.append("must not run"), timeout=0.01)
        release.set()
        first.join(timeout=1.0)
        assert not calls
        assert not errors
    finally:
        release.set()
        host.close(timeout=30.0)


def test_host_can_submit_from_worker_thread_without_deadlock() -> None:
    host = StaExecutorHost(lambda: RecordingExecutor())
    host.start()
    try:
        assert host.submit(lambda: host.submit(lambda: "nested")) == "nested"
    finally:
        host.close(timeout=30.0)


def test_host_close_waits_for_queued_commands_before_disconnect() -> None:
    events: list[str] = []
    host = StaExecutorHost(lambda: RecordingExecutor(events))
    host.start()
    try:
        host.submit(lambda: events.append("first"))
        host.submit(lambda: (time.sleep(0.01), events.append("second")))
    finally:
        host.close(timeout=30.0)

    assert events[-1] == "disconnected"


def test_host_close_drains_queued_commands_before_disconnect() -> None:
    started = threading.Event()
    release = threading.Event()
    events: list[str] = []
    errors: list[BaseException] = []
    host = StaExecutorHost(lambda: RecordingExecutor(events))
    host.start()

    def blocking() -> None:
        events.append("first")
        started.set()
        release.wait(timeout=30.0)

    def queued() -> None:
        try:
            host.submit(lambda: events.append("second"))
        except BaseException as exc:
            errors.append(exc)

    try:
        first_thread = threading.Thread(target=lambda: host.submit(blocking))
        first_thread.start()
        assert started.wait(timeout=1.0)
        queued_thread = threading.Thread(target=queued)
        queued_thread.start()
        time.sleep(0.01)
        close_thread = threading.Thread(target=lambda: host.close(timeout=30.0))
        close_thread.start()
        release.set()
        close_thread.join(timeout=1.0)
        queued_thread.join(timeout=1.0)
        assert not errors
        assert events == ["created", "first", "second", "disconnected"]
    finally:
        release.set()
        first_thread.join(timeout=1.0)
        if host.state is not HostState.CLOSED:
            host.close(timeout=30.0)
