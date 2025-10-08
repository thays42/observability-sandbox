## Goals
- [ ] Setup real-time monitoring of applications
    - [ ] System performance
    - [ ] Application activity
    - [ ] Key metrics

Application / system health (start/stop/crash/restart)
    - Heartbeat / status check
    - Alerts!

For one particular user: how do they use our applications? User behavior across apps
    - Are people using/not using a particular app or feature?
    - Are there "app sequences"?

For a given application: how do users use that application?
    - How can we make products better for users?

Are apps breaking?

What role does kafka play / how to handle events that contribute to observability, but are used elsewhere too.
    - We need apps that care to consume from kafka (further from where we are right now)

Reporting
    - What do you want to know?
        - Adoption
        - Who to ask: Mike D., Ernest, Phil, Ren, (stakeholders), (practice area leaders), (product managers)
        - We are intensely investigating how we do observability, this is a very useful input at this stage of the exploration.
    - What information / data do we need from apps?
    - What periodicity for reports?
    - What format?  (PDF, HTML, PPT, XLSX)
    - Which apps?
    - For whom?

Why traces?
    - One app
    - Multiple apps


## By Component

### Structure

- [ ] Separate observability stack and demo apps into their own compose projects

### Loki

- [X] Add loki
- [ ] What kind of dashboards make sense for logs?
- [ ] How can metrics and logs be combined in grafana?
- [ ] Can loki parse logs into structured data in a database?
- [ ] Analyze loki data to Python

### User/session activity tracking

- [ ] Add user login to Shiny application
- [X] Add user session to dice roll application
- [ ] How do we track user activity in a single application?
- [ ] How do we track user activity across applications?

### Prometheus

- [ ] Expose docker metrics to prometheus
- [ ] Export loki metrics to prometheus

### Grafana

- [ ] Can grafana create reports?
- [ ] Grafana alerts

### Kafka

- [ ] Add kafka
- [ ] Connect kafka to grafana
