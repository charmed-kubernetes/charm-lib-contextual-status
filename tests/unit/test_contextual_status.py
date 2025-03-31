import logging
import unittest.mock as mock
import ops
import ops.testing
import pytest
import charms.contextual_status as context_status


@pytest.fixture
def harness():
    harness = ops.testing.Harness(ops.CharmBase, meta='{"name": "test-charm"}')
    harness.begin_with_initial_hooks()
    harness._get_backend_calls(reset=True)
    yield harness
    harness.cleanup()


@mock.patch("charms.contextual_status.contexts", new=None)
def test_add_outside_context(caplog):
    context_status.add(ops.MaintenanceStatus("Testing"))
    assert "Could not add status outside of a status context" in caplog.text


def test_add_single_context(harness, caplog):
    unit = harness.charm.unit
    successfully_exit = ops.ActiveStatus("Exit")
    inner = ops.MaintenanceStatus("Testing Inner")

    with context_status.context(unit, exit_status=successfully_exit):
        context_status.add(inner)

    calls = harness._get_backend_calls()
    assert calls == [
        ("status_set", "maintenance", "Testing Inner", {"is_app": False}),
        ("status_set", "active", "Exit", {"is_app": False}),
    ]
    assert not caplog.text


def test_add_multiple_contexts(harness, caplog):
    unit = harness.charm.unit
    successfully_exit = ops.ActiveStatus("Exit")
    before = ops.MaintenanceStatus("Before")
    inner = ops.MaintenanceStatus("Inner")
    after = ops.MaintenanceStatus("After")

    with context_status.context(unit, exit_status=successfully_exit):
        context_status.add(before)
        with context_status.context(unit, exit_status=successfully_exit):
            context_status.add(inner)
        context_status.add(after)

    calls = harness._get_backend_calls()
    assert calls == [
        ("status_set", "maintenance", "Before", {"is_app": False}),
        ("status_set", "maintenance", "Inner", {"is_app": False}),
        ("status_set", "maintenance", "Inner", {"is_app": False}),
        ("status_set", "active", "Exit", {"is_app": False}),
        ("status_set", "maintenance", "After", {"is_app": False}),
        ("status_set", "active", "Exit", {"is_app": False}),
    ]
    assert "Already in a status context, proceeding anyway" in caplog.text


@pytest.mark.parametrize("status_type", [ops.BlockedStatus, ops.WaitingStatus])
def test_add_multiple_same_type(harness, caplog, status_type):
    unit = harness.charm.unit
    ignored = status_type("Ignored")
    seen = status_type("Seen")

    with context_status.context(unit):
        context_status.add(seen)
        # add any other status of the same type is ignored
        context_status.add(ignored)

    calls = harness._get_backend_calls()
    assert calls == [("status_set", status_type.name, "Seen", {"is_app": False})]
    assert not caplog.text


def test_add_waiting_and_blocked(harness, caplog):
    unit = harness.charm.unit
    ignored = ops.WaitingStatus("Ignored")
    seen = ops.BlockedStatus("Seen")

    with context_status.context(unit):
        context_status.add(ignored)
        # blocked status has a higher priority
        context_status.add(seen)

    calls = harness._get_backend_calls()
    assert calls == [("status_set", "blocked", "Seen", {"is_app": False})]
    assert not caplog.text


def test_add_multiple_waiting(harness, caplog):
    unit = harness.charm.unit
    successfully_exit = ops.ActiveStatus("Exit")
    ignored = ops.WaitingStatus("Ignored")
    seen = ops.WaitingStatus("Seen")

    with context_status.context(unit, exit_status=successfully_exit):
        context_status.add(seen)
        # any other add waiting status is ignored
        context_status.add(ignored)

    calls = harness._get_backend_calls()
    assert calls == [("status_set", "waiting", "Seen", {"is_app": False})]
    assert not caplog.text


@mock.patch("charms.contextual_status.add")
def test_on_error_translates_all_exceptions_to_reconciler_error(added, caplog):
    caplog.set_level(logging.DEBUG)
    wait = ops.WaitingStatus("wait")
    with pytest.raises(context_status.ReconcilerError):
        with context_status.on_error(wait):
            raise ZeroDivisionError("test")
    added.assert_called_once_with(wait)
    assert "Found expected exception: test" in caplog.text


@mock.patch("charms.contextual_status.add")
def test_on_error_dont_block_unknown_exceptions(added, caplog):
    caplog.set_level(logging.DEBUG)
    wait = ops.WaitingStatus("wait")
    with pytest.raises(ZeroDivisionError):
        with context_status.on_error(wait, ValueError):
            raise ZeroDivisionError("test")
    added.assert_not_called()
    assert not caplog.text
