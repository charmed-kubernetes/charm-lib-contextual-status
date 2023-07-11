import logging

from contextlib import contextmanager
from ops import ActiveStatus, BlockedStatus, WaitingStatus

contexts = []
log = logging.getLogger(__name__)


def add(status):
    """ Add unit status to the current context.

    If status is MaintenanceStatus, then it is assigned to the unit immediately
    so the charm can provide in-progress updates.

    If status is BlockedStatus or WaitingStatus, then it is stored in the status
    context for later, to be assigned to the unit when the context is closed.
    """
    if not contexts:
        log.warning(f"Could not add status outside of a status context: {status}")
        return

    for context in contexts:
        if type(status) == BlockedStatus:
            context["blocked"].append(status)
        elif type(status) == WaitingStatus:
            context["waiting"].append(status)
        else:
            context["unit"].status = status


@contextmanager
def context(unit):
    """ Create a status context.

    Status contexts are used to collect Blocked or Waiting statuses that are
    raised within the context lifecycle. Any calls to the add() function with
    Blocked or Waiting statuses will be captured by the context.

    When the context is closed, unit status is set according to a priority
    order, preferring Blocked status over Waiting. The earliest Status that
    is set will be used.

    Multiple contexts can be nested, in which case each active context will
    capture every status that is raised within. This usage isn't recommended
    however.
    """
    if contexts:
        log.warning("Already in a status context, proceeding anyway")

    context = {"unit": unit, "blocked": [], "waiting": []}
    contexts.append(context)

    try:
        yield
    finally:
        contexts.pop()
        statuses = context['blocked'] + context['waiting']
        log.info(f"Status context closed with: {statuses}")
        unit.status = statuses[0] if statuses else ActiveStatus()


@contextmanager
def on_error(status):
    """ Context for emitting status on error.

    If an exception occurs within the on_error context body, then add the
    specified status to the status context. This can be used as a function
    decorator to emit Blocked or Waiting status on error with less try/except
    boilerplate.
    """
    try:
        yield
    except Exception:
        add(status)
        raise
