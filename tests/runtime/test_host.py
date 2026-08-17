from __future__ import annotations

import threading
import time
from collections import deque

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
    with pytest.raises(RuntimeError, match="cannot create"):
        host.start()

    assert host.state is HostState.FAILED
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
