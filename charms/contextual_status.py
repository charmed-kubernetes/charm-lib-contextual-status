import logging
import ops
from contextlib import contextmanager
from typing import List, Optional, Type, TypedDict

log = logging.getLogger(__name__)


class Context(TypedDict):
    unit: ops.Unit
    blocked: List[ops.BlockedStatus]
    waiting: List[ops.WaitingStatus]


contexts: List[Context] = []


def add(status: ops.StatusBase):
    """Add unit status to the current context.

    If status is MaintenanceStatus, then it is assigned to the unit immediately
    so the charm can provide in-progress updates.

    If status is BlockedStatus or WaitingStatus, then it is stored in the status
    context for later, to be assigned to the unit when the context is closed.
    """
    if not contexts:
        log.warning(f"Could not add status outside of a status context: {status}")
        return

    for context in contexts:
        if isinstance(status, ops.BlockedStatus):
            context["blocked"].append(status)
        elif isinstance(status, ops.WaitingStatus):
            context["waiting"].append(status)
        else:
            context["unit"].status = status


@contextmanager
def context(unit: ops.Unit, exit_status: Optional[ops.StatusBase] = None):
    """Create a status context.

    Status contexts are used to collect Blocked or Waiting statuses that are
    raised within the context lifecycle. Any calls to the add() function with
    Blocked or Waiting statuses will be captured by the context.

    When the context is closed, unit status is set according to a priority
    order, preferring Blocked status over Waiting. The earliest Status that
    is set will be used. If no statuses are set, the specified exit_status is used.

    Multiple contexts can be nested, in which case each active context will
    capture every status that is raised within. This usage isn't recommended
    however.

    Args:
        unit (Unit): The unit whose status is being managed.
        exit_status (StatusBase, optional): The status to set when the exiting
        the context if no other status is set. Defaults to ActiveStatus(Ready)
    """
    exit_status = exit_status or ops.ActiveStatus("Ready")

    if contexts:
        log.warning("Already in a status context, proceeding anyway")

    context: Context = {"unit": unit, "blocked": [], "waiting": []}
    contexts.append(context)

    try:
        yield
    finally:
        contexts.pop()
        statuses = context["blocked"] + context["waiting"]
        log.info(f"Status context closed with: {statuses}")
        unit.status = statuses[0] if statuses else exit_status


class ReconcilerError(Exception):
    """
    Raised by the on_error context when the charm translates
    a known|expected error into a Waiting or Blocked Status.

    on_error allows the charm developer to escape the reconcile
    loop by raising expected exceptions, which will be translated
    into charm status conditions.
    """

    pass


@contextmanager
def on_error(status: ops.StatusBase, *status_exceptions: Type[Exception]):
    """Context for emitting status on error.

    If an exception occurs within the on_error context body, then add the
    specified status to the status context. This can be used as a function
    decorator to emit Blocked or Waiting status on error with less try/except
    boilerplate.

    By default, on_error catches all exceptions, but it can be tuned to only
    catch specific exception types passed in status_exceptions.  When tuned,
    the status is only added to the context on the passed exceptions, and other
    exceptions won't be caught
    """
    status_exceptions = status_exceptions or (Exception,)

    try:
        yield
    except status_exceptions as e:
        msg = f"Found expected exception: {e}"
        log.debug(msg)
        add(status)
        raise ReconcilerError(msg) from e
