## Objectives

In addition to observability, I am interested in storing usage data for ad hoc analysis and periodic reporting. To achieve this, I want to add the following to the observability stack:

1. A Postgresql database.
2. A HTTP receiver service to receive log events from Alloy and incorporate them into the database.
3. A component to Alloy to route certain log events to the HTTP receiver.

## Specifications

### Postgresql database

The Postgresql database has a single table, `usage_stats`, which has one JSON field. Each log event will be a single record in this table.

### HTTP receiver

The HTTP receiver receives log events from Alloy and appends them to the `usage_stats` table in the Postgresql database.

### Alloy component

When Alloy receives log events, it should check to see if it contains the field `usage`, and if that field is `true`. If that is the case, the log event should be routed to the HTTP receiver in addition to the observability stack. All other log events should continue to route to the observability stack.