## Objectives

We want to create a progressively complicated family of services implemented in Python to demonstrate:

1. How to instrument Python code using OpenTelemetry.
2. How to collect that OpenTelemetry data and route it to an observability stack.
3. How to analyze that OpenTelemetry data once it is in the observability stack.

While we will add complexity in stages, the goal is for each stage to be simple enough to understand but nontrivial enough to demonstrate the use cases of instrumentation and observability.

## Stages

We will pursue this objective through stages. At the end of every stage, we will:

1. Have a functional system of one or more applications, launched as a docker compose project, with instrumented to generate metrics, logs, and traces using OpenTelemetry.
2. Have a useful and meaningful set of dashboards and means of querying our observability data in Grafana.
3. Have a means of create synthetic traffic to generate data for our observability stack.

### Stage 1: Single FastAPI Service (Die rolling service)

#### Application specifications

In this initial stage, we will establish the foundation to which we will add in later stages.

The API should have one functional endpoint: `/roll`. This endpoint takes a required string parameter (`die`) that must be one of "fair" or "risky".

This endpoint simulates the rolling of a 6-sided die. It returns roll as a JSON object, e.g., `{"roll": 5}`. When  `die` is "fair", the service simulates a fair die. When `die` is "risky", the simulates a die that always adds 1 to each roll and has a 10% chance each roll to error out, producing a 500 response. The service will add a random amount of wait time, up to 1 second, before responding.

#### Instrumentation

TODO

#### Traffic generation

To generate traffic, use a Python script that can specify:

1. NUM_USERS: Number of users to simulate
1. MAX_ROLLS_PER_USER: Maximum number of rolls to simulate per user

The script will asynchronously simulate NUM_USERS users, labeled User 1, User 2, etc.. For each user, it will pick a random integer between 1 and MAX_ROLLS_PER_USER to represent the number of rolls that user will make. For each roll, the user picks with equal probability whether to use the `/fair` or `/risky` endpoint. After a user receives the result of its last roll, the script will log that the user has finished its last roll. Once the last user finishes, the script logs that the traffic generation process is complete.

#### Grafana dashboards

TODO

### Stage 2: Add a Streamlit frontend

In this stage, we add a Streamlit frontend that can be used to to interact with the backend. The frontend provides a drop down (Risky or Fair) and a Run button on one row, and an output literal textbox on a separate row. When the user presses the Run button, the frontend sends the corresponding request to the backend and populates the output literal textbox with the response status code and body.

#### Instrumentation

TODO

#### Traffic generation

TODO

#### Grafana dashboards

TODO

### Stage 3: Add another FastAPI Service (Die service)

In this stage, we add another FastAPI frontend that will provide specifications for 6 sided die. These specifications include the face values and an error rate. For ease of development, these specifications are stored in a JSON file and loaded into the service at launch. For example, the following specification file describes the fair and risky die:

```
{
    "fair": {
        "faces": [1,2,3,4,5,6],
        "error_rate": 0
    },
    "risky": {
        "faces": [2,3,4,5,6,7],
        "error_rate": 0.1
    }
}
```

This service should provide a single endpoint (`/dice`) that takes an optional string parameter `identifier`. When no `identifier` is specified, the service returns a list containing all valid identifiers, e.g., `{"identifiers": ["fair", "risky"]}`. When specified, the service returns the corresponding specification. Specifying an unknown identifier returns an error code.

Our Frontend changes by using the Die service to populate the dropdown.

Our Roll service changes by looking up the die specification from the Die service.

#### Instrumentation

TODO

#### Traffic generation

TODO

#### Grafana dashboards

TODO

### Stage 4: Async Rolling

In this stage, we add a `/roll-async` endpoint to the rolling service. This endpoint works similar to the `/roll` endpoint, but takes an additional parameter, `times`, indicating the number of die to roll. The rolling service will make these rolls asynchronously, then return the total of the rolls.

#### Instrumentation

TODO

#### Traffic generation

TODO

#### Grafana dashboards

TODO

### Stage 5: Die database

In this stage, we add a database backend for the Die service. The database is seeded with the JSON file specifying all the die, and instead of the Die service storing and looking up information in-memory, it queries the database.

#### Instrumentation

TODO

#### Traffic generation

TODO

#### Grafana dashboards

TODO

### Stage 6: Usage Tracking

In this stage, we add some usage tracking. This stage has nothing to do with observability but demonstrates how you can route specific log messages to a different location.

To achieve this, we will need to have add some instrumentation to the frontend where we include the field `"usage": true` in log events specifically designed for usage tracking. 

We'll add a dead simple sign-in flow to the streamlit app. We will include `"usage": true` to log events corresponding to:

1. Sign-in
2. Run

