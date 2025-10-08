FROM rocker/r-ver:4.5.1

# Install system dependencies for R packages and OpenTelemetry C++ SDK
RUN apt-get update && apt-get install -y --no-install-recommends \
    libcurl4-openssl-dev \
    libssl-dev \
    cmake \
    patch \
    protobuf-compiler \
    libprotobuf-dev \
    && rm -rf /var/lib/apt/lists/*

# Install shiny, httr2, logger, uuid, jsonlite, otel, and otelsdk from Posit Package Manager (pre-built binaries for Ubuntu)
RUN R -e "install.packages(c('shiny', 'httr2', 'logger', 'uuid', 'jsonlite', 'otel', 'otelsdk'), repos='https://packagemanager.posit.co/cran/__linux__/noble/latest')"

# Create app directory
RUN mkdir -p /app

# Copy the app
COPY app.R /app/

# Set working directory
WORKDIR /app

# Expose Shiny port
EXPOSE 3838

# Run the app directly with R
CMD ["R", "-e", "shiny::runApp('/app', host='0.0.0.0', port=3838)"]