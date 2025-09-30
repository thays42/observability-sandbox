library(shiny)
library(httr2)

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
  # Reactive value to store response
  response_text <- eventReactive(input$run, {
    # Validate URL
    if (is.null(input$url) || input$url == "") {
      return("Error: URL cannot be empty")
    }

    tryCatch(
      {
        # Build request based on HTTP method
        req <- request(input$url)

        message("Method selected:", input$action, "\n")
        message("URL:", input$url, "\n")

        resp <- req |>
          req_method(input$action) |>
          req_perform()

        message("Response received, status:", resp_status(resp), "\n")

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
