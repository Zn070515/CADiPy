from __future__ import annotations

import sys
import threading
import time
from concurrent.futures import Future

import pytest

from cadipy.domain.errors import SessionClosedError, WorkerError
from cadipy.runtime.host import ExecutorHost, HostState, StaExecutorHost


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
        assert isinstance(host, ExecutorHost)
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


def test_host_launch_failure_is_prompt_stable_and_safe_to_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    launch_error = RuntimeError("thread launch failed")
    original_start = threading.Thread.start
    errors: list[BaseException] = []
    host = StaExecutorHost(
        lambda: RecordingExecutor(),
        apartment_init=lambda: None,
        apartment_uninit=lambda: None,
    )

    def fail_worker_start(thread: threading.Thread) -> None:
        if thread is host._worker:
            raise launch_error
        original_start(thread)

    monkeypatch.setattr(threading.Thread, "start", fail_worker_start)

    def start_host() -> None:
        try:
            host.start()
        except BaseException as exc:
            errors.append(exc)

    start_thread = threading.Thread(target=start_host, daemon=True)
    start_thread.start()
    start_thread.join(timeout=1.0)

    assert not start_thread.is_alive()
    assert len(errors) == 1
    assert isinstance(errors[0], WorkerError)
    assert errors[0].__cause__ is launch_error
    assert host.state is HostState.FAILED
    assert not host._worker.is_alive()
    host.close(timeout=30.0)


def test_host_default_apartment_is_portable_without_pythoncom(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(sys.modules, "pythoncom", None)
    host = StaExecutorHost(lambda: RecordingExecutor())
    host.start()
    try:
        assert host.submit(lambda: "portable") == "portable"
    finally:
        host.close(timeout=30.0)


def test_host_worker_loop_failure_rejects_pending_work() -> None:
    loop_error = RuntimeError("queue loop failed")
    factory_started = threading.Event()
    release_factory = threading.Event()
    pending_future: Future[str] = Future()
    host = StaExecutorHost(
        lambda: (
            factory_started.set(),
            release_factory.wait(timeout=1.0),
            RecordingExecutor(),
        )[2],
        apartment_init=lambda: None,
        apartment_uninit=lambda: None,
    )
    original_get = host._commands.get
    first_get = True

    def failing_get(*, block: bool = True, timeout: float | None = None) -> object:
        nonlocal first_get
        if first_get:
            first_get = False
            raise loop_error
        return original_get(block=block, timeout=timeout)

    host._commands.get = failing_get  # type: ignore[method-assign]
    start_thread = threading.Thread(target=host.start)
    start_thread.start()
    assert factory_started.wait(timeout=1.0)
    host._commands.put((lambda: "pending", pending_future))
    release_factory.set()

    start_thread.join(timeout=1.0)
    assert not start_thread.is_alive()

    for _ in range(100):
        if host.state is HostState.FAILED:
            break
        time.sleep(0.01)

    assert host.state is HostState.FAILED
    with pytest.raises(WorkerError) as exc_info:
        pending_future.result(timeout=1.0)
    assert exc_info.value.__cause__ is loop_error
    host.close(timeout=30.0)


def test_host_startup_failure_rejects_accepted_commands_before_completion() -> None:
    startup_error = RuntimeError("factory failed")
    factory_started = threading.Event()
    release_factory = threading.Event()
    command_accepted = threading.Event()
    command_done = threading.Event()
    start_errors: list[BaseException] = []
    command_errors: list[BaseException] = []
    host = StaExecutorHost(
        lambda: (
            factory_started.set(),
            release_factory.wait(timeout=1.0),
            (_ for _ in ()).throw(startup_error),
        )[2],
        apartment_init=lambda: None,
        apartment_uninit=lambda: None,
    )
    original_put = host._commands.put

    def acknowledge_put(item: object, *args: object, **kwargs: object) -> None:
        original_put(item, *args, **kwargs)
        if item is not None:
            command_accepted.set()

    host._commands.put = acknowledge_put  # type: ignore[method-assign]

    def submit_command() -> None:
        try:
            host.submit(lambda: "must not run")
        except BaseException as exc:
            command_errors.append(exc)
        finally:
            command_done.set()

    def start_host() -> None:
        try:
            host.start()
        except BaseException as exc:
            start_errors.append(exc)

    start_thread = threading.Thread(target=start_host, daemon=True)
    start_thread.start()
    assert factory_started.wait(timeout=1.0)
    command_thread = threading.Thread(target=submit_command, daemon=True)
    command_thread.start()
    assert command_accepted.wait(timeout=1.0)
    release_factory.set()

    start_thread.join(timeout=1.0)
    command_thread.join(timeout=1.0)
    assert not start_thread.is_alive()
    assert command_done.is_set()
    assert len(start_errors) == 1
    assert isinstance(start_errors[0], WorkerError)
    assert start_errors[0].__cause__ is startup_error
    assert len(command_errors) == 1
    assert isinstance(command_errors[0], WorkerError)
    assert command_errors[0].__cause__ is startup_error
    assert host.state is HostState.FAILED
    host.close(timeout=30.0)


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
    queued_accepted = threading.Event()
    queued_done = threading.Event()
    queued_errors: list[BaseException] = []
    first_errors: list[BaseException] = []

    def blocking() -> None:
        started.set()
        release.wait(timeout=30.0)

    host = StaExecutorHost(lambda: RecordingExecutor())
    original_put = host._commands.put

    def acknowledge_put(item: object, *args: object, **kwargs: object) -> None:
        original_put(item, *args, **kwargs)
        if item is not None and item[0] is queued_command:  # type: ignore[index]
            queued_accepted.set()

    def queued_command() -> None:
        raise AssertionError("queued command must not run")

    host._commands.put = acknowledge_put  # type: ignore[method-assign]
    host.start()
    try:

        def submit_blocking() -> None:
            try:
                host.submit(blocking)
            except BaseException as exc:
                first_errors.append(exc)

        def submit_queued() -> None:
            try:
                host.submit(queued_command)
            except BaseException as exc:
                queued_errors.append(exc)
            finally:
                queued_done.set()

        first = threading.Thread(target=submit_blocking)
        first.start()
        assert started.wait(timeout=1.0)
        queued = threading.Thread(target=submit_queued)
        queued.start()
        assert queued_accepted.wait(timeout=1.0)
        with pytest.raises(TimeoutError):
            host.submit(lambda: None, timeout=0.01)
        assert queued_done.wait(timeout=1.0)
        assert len(queued_errors) == 1
        assert isinstance(queued_errors[0], WorkerError)
        assert not first_errors
        release.set()
        first.join(timeout=1.0)
        queued.join(timeout=1.0)
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
        host.submit(lambda: events.append("second"))
    finally:
        host.close(timeout=30.0)

    assert events[-1] == "disconnected"


def test_host_close_drains_queued_commands_before_disconnect() -> None:
    started = threading.Event()
    release = threading.Event()
    events: list[str] = []
    errors: list[BaseException] = []
    host = StaExecutorHost(lambda: RecordingExecutor(events))
    queued_accepted = threading.Event()
    original_put = host._commands.put

    def acknowledge_put(item: object, *args: object, **kwargs: object) -> None:
        original_put(item, *args, **kwargs)
        if item is not None and item[0] is second_command:  # type: ignore[index]
            queued_accepted.set()

    host._commands.put = acknowledge_put  # type: ignore[method-assign]
    host.start()

    def blocking() -> None:
        events.append("first")
        started.set()
        release.wait(timeout=30.0)

    def second_command() -> None:
        events.append("second")

    def queued() -> None:
        try:
            host.submit(second_command)
        except BaseException as exc:
            errors.append(exc)

    try:
        first_thread = threading.Thread(target=lambda: host.submit(blocking))
        first_thread.start()
        assert started.wait(timeout=1.0)
        queued_thread = threading.Thread(target=queued)
        queued_thread.start()
        assert queued_accepted.wait(timeout=1.0)
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
