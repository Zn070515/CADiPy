from __future__ import annotations

import threading

import pytest

from .test_part_extrude_roundtrip import run_rectangular_contract_via_session


@pytest.mark.solidworks
@pytest.mark.real_solidworks
def test_roundtrip_executes_through_one_sta_session(
    solidworks_session,
    solidworks_executor_factory,
    tmp_path,
) -> None:
    result = run_rectangular_contract_via_session(solidworks_session, tmp_path)

    assert result.ok is True
    assert result.execution is not None
    assert result.execution.phase.value == "committed"
    operation_thread_ids = tuple(solidworks_executor_factory.operation_thread_ids)
    assert operation_thread_ids
    assert len(set(operation_thread_ids)) == 1
    assert operation_thread_ids[0] != threading.get_ident()
    assert solidworks_executor_factory.executor_creation_thread_ids == [operation_thread_ids[0]]
