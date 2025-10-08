library(shiny)
library(httr2)
library(logger)
library(uuid)
library(jsonlite)
# Note: Don't load library(otel) to avoid conflicts with logger package
# Instead, use otel:: prefix for all otel functions

# Note: otelsdk tracer provider is configured automatically via environment variables
# OTEL_EXPORTER_OTLP_TRACES_ENDPOINT is read by otelsdk at startup

# Get tracer for this application
app_tracer <- otel::get_tracer("shiny-curl-gui")

# Configure logger with custom JSON layout
log_formatter(formatter_json)
log_threshold(DEBUG)
log_layout(layout_json_parser(fields = c("level")))

# Helper function to get trace context from span object
get_trace_context_from_span <- function(span) {
  # Get context using the span's get_context() method
  if (is.null(span)) {
    return(NULL)
  }

  ctx <- span$get_context()
  if (is.null(ctx)) {
    return(NULL)
  }

  list(
    trace_id = ctx$get_trace_id(),
    span_id = ctx$get_span_id()
  )
}

# Log application startup (no session_id at this point)
log_info(msg = "Shiny application ready and accessible")

# UI Definition
ui <- fluidPage(
  titlePanel("cURL GUI"),

  fluidRow(
    column(
      2,
      selectInput(
        "action",
        "Method:",
        choices = c("GET", "POST", "PUT", "DELETE"),
        selected = "GET"
      )
    ),
    column(
      8,
      textInput(
        "url",
        "URL:",
        value = "http://demo-fastapi-rolldice:8001/roll/2d6",
        width = "100%"
      )
    ),
    column(
      2,
      actionButton("run", "Run", style = "margin-top: 25px; width: 100%;")
    )
  ),

  fluidRow(
    column(
      12,
      h4("Response:"),
      # TODO: Add request body input for POST/PUT methods
      # TODO: Add custom headers input
      verbatimTextOutput("response")
    )
  )
)

# Server Logic
server <- function(input, output, session) {
  # Generate unique session ID
  session_id <- UUIDgenerate()

  # Log session start
  log_info(msg = "Session started", session_id = session_id)

  # Log session end when session closes
  onSessionEnded(function() {
    log_info(msg = "Session ended", session_id = session_id)
  })

  # Reactive value to store response
  response_text <- eventReactive(input$run, {
    # Validate URL
    if (is.null(input$url) || input$url == "") {
      return("Error: URL cannot be empty")
    }

    # Create initial span attributes
    span_attrs <- list(
      "http.method" = input$action,
      "http.url" = input$url
    )

    # Create a span for the HTTP request with attributes
    span <- otel::start_local_active_span(
      paste0("HTTP ", input$action, " ", input$url),
      tracer = app_tracer,
      attributes = span_attrs
    )

    # Get trace context from the span for logging
    trace_ctx <- get_trace_context_from_span(span)

    # Log HTTP request initiation with trace context
    log_args <- list(
      msg = "HTTP request initiated",
      session_id = session_id,
      method = input$action,
      url = input$url
    )
    if (!is.null(trace_ctx)) {
      log_args$trace_id <- trace_ctx$trace_id
      log_args$span_id <- trace_ctx$span_id
    }
    do.call(log_debug, log_args)

    tryCatch(
      {
        # Build request based on HTTP method
        req <- request(input$url)

        resp <- req |>
          req_method(input$action) |>
          req_perform()

        status_code <- resp_status(resp)

        # Note: R otel package doesn't support setting attributes after span creation
        # We'll add status_code in a future span or use events if needed

        # Log response with appropriate level based on status code
        log_args <- list(
          msg = "HTTP response received",
          session_id = session_id,
          method = input$action,
          url = input$url,
          status_code = status_code
        )
        if (!is.null(trace_ctx)) {
          log_args$trace_id <- trace_ctx$trace_id
          log_args$span_id <- trace_ctx$span_id
        }

        if (status_code >= 500) {
          # Note: R otel package doesn't have set_span_status yet
          do.call(log_error, log_args)
        } else if (status_code >= 400) {
          do.call(log_warn, log_args)
        } else {
          do.call(log_info, log_args)
        }

        # Format response
        status_line <- sprintf("Status Code: %d", resp_status(resp))

        # Format headers
        headers <- resp_headers(resp)
        header_lines <- sapply(names(headers), function(name) {
          sprintf("  %s: %s", name, headers[[name]])
        })
        headers_text <- paste(
          "Headers:",
          paste(header_lines, collapse = "\n"),
          sep = "\n"
        )

        # Get body
        body_text <- tryCatch(
          {
            body <- resp_body_string(resp)
            if (nchar(body) > 0) {
              sprintf("Body:\n%s", body)
            } else {
              "Body: (empty)"
            }
          },
          error = function(e) {
            "Body: (unable to parse)"
          }
        )

        # Combine all parts
        paste(status_line, headers_text, body_text, sep = "\n\n")
      },
      error = function(e) {
        sprintf("Error: %s", conditionMessage(e))
      }
    )
  })

  output$response <- renderText({
    response_text()
  })
}

# Run the application
shinyApp(ui = ui, server = server)
