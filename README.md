# charm-lib-contextual-status

Contextual status handling for charmed operators.

The goal of this library is to provide a mechanism for code within charm
libraries to raise status conditions, such as Blocked or Waiting statuses,
without relying on exceptions or other constructs that might otherwise interfere
with the flow control of Python code.

This is accomplished by having the charm create a background status context with:

```python3
import charms.contextual_status as status

with status.context(self.unit):
    some_lib.do_work()
```

Within a status context, it's possible for code to emit status conditions:

```python3
status.add(MaintenanceStatus("Doing something"))

if some_failure_condition:
    status.add(BlockedStatus("Failed to do something"))
```

When a `MaintenanceStatus` is added to a status context, it is immediately
set as the unit status, so that the charm can provide status updates during
in-progress work.

When a `BlockedStatus` or `WaitingStatus` is added to a status context, it is
stored within the context for later. Multiple statuses can be added this way.

When a status context is closed, the unit status is set based on a simple
priority system: `Blocked` status is higher precedence than `Waiting`, and
within those groups, the earliest emitted status is preferred. If no `Blocked`
or `Waiting` statuses were emitted within the context, then the unit status is
set to `Active`.

The `on_error` decorator can be used to set status when an exception is raised:

```python3
@status.on_error(BlockedStatus("Failed to do something"))
def do_something():
    status.add(MaintenanceStatus("Doing something"))

    # ...
```
