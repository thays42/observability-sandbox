import logging
import json
import threading
import requests
import streamlit as st
from prometheus_client import Counter, Histogram, start_http_server

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.instrumentation.requests import RequestsInstrumentor
from opentelemetry.propagate import inject


# Custom JSON formatter for structured logging with trace context
class JSONFormatter(logging.Formatter):
    def format(self, record):
        log_data = {
            "timestamp": self.formatTime(record, datefmt="%Y-%m-%dT%H:%M:%S.%fZ"),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
        }

        # Add trace context
        span = trace.get_current_span()
        if span.get_span_context().is_valid:
            ctx = span.get_span_context()
            log_data["trace_id"] = format(ctx.trace_id, "032x")
            log_data["span_id"] = format(ctx.span_id, "016x")

        # Add any extra fields from record
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        return json.dumps(log_data)


# Configure logging
logger = logging.getLogger(__name__)
handler = logging.StreamHandler()
handler.setFormatter(JSONFormatter())
logger.addHandler(handler)
logger.setLevel(logging.INFO)

# Initialize OpenTelemetry tracing
trace.set_tracer_provider(TracerProvider())
otlp_exporter = OTLPSpanExporter(endpoint="http://otel-collector:4318/v1/traces")
trace.get_tracer_provider().add_span_processor(BatchSpanProcessor(otlp_exporter))
tracer = trace.get_tracer(__name__)

# Instrument requests library for automatic trace propagation
RequestsInstrumentor().instrument()

# Custom Prometheus metrics
button_clicks_total = Counter(
    "streamlit_button_clicks_total", "Total number of button clicks", ["die_type"]
)

requests_total = Counter(
    "streamlit_requests_total",
    "Total number of backend requests",
    ["die_type", "status_code"],
)

request_duration_seconds = Histogram(
    "streamlit_request_duration_seconds",
    "Backend request duration in seconds",
    ["die_type"],
    buckets=[0.1, 0.25, 0.5, 0.75, 1.0, 1.5, 2.0, 3.0],
)


# Start Prometheus metrics HTTP server (only once)
# Use Streamlit's singleton to ensure it only starts once
@st.cache_resource
def start_metrics_server():
    """Start Prometheus HTTP server on port 9090."""
    start_http_server(9090)
    logger.info("Metrics server started on port 9090")
    return True


# Initialize metrics server
start_metrics_server()

# Log application startup
logger.info("Streamlit frontend starting up")

# Streamlit UI
st.title("🎲 Dice Roller")
st.write("Roll dice using the backend API")

# Configuration
BACKEND_URL = "http://dice-roller-stage2:8000"

# Die type selection
die_type = st.selectbox(
    "Select die type:",
    options=["fair", "risky"],
    help="Fair: standard 1-6 die. Risky: 2-7 die with 10% error chance",
)

# Roll button
if st.button("Roll", type="primary"):
    # Record button click
    button_clicks_total.labels(die_type=die_type).inc()

    # Create span for the roll operation
    with tracer.start_as_current_span("roll_button_click") as span:
        span.set_attribute("die.type", die_type)

        # Log button click
        logger.info("Button clicked", extra={"extra_fields": {"die_type": die_type}})

        # Make request to backend with trace context propagation
        headers = {}
        inject(headers)  # Inject W3C Trace Context headers

        try:
            import time

            start_time = time.time()

            response = requests.get(
                f"{BACKEND_URL}/roll",
                params={"die": die_type},
                headers=headers,
                timeout=5.0,
            )

            duration = time.time() - start_time

            # Record metrics
            requests_total.labels(
                die_type=die_type, status_code=response.status_code
            ).inc()
            request_duration_seconds.labels(die_type=die_type).observe(duration)

            # Add response details to span
            span.set_attribute("backend.status_code", response.status_code)
            span.set_attribute("backend.url", f"{BACKEND_URL}/roll")

            if response.status_code == 200:
                result = response.json()
                roll_value = result.get("roll")

                # Log successful response
                logger.info(
                    "Backend response received",
                    extra={
                        "extra_fields": {
                            "die_type": die_type,
                            "backend_status": response.status_code,
                            "roll_value": roll_value,
                        }
                    },
                )

                # Display result
                st.success(f"🎲 You rolled: **{roll_value}**")

                # Show trace info
                if span.get_span_context().is_valid:
                    ctx = span.get_span_context()
                    trace_id = format(ctx.trace_id, "032x")
                    with st.expander("🔍 Trace Info"):
                        st.code(f"Trace ID: {trace_id}")
                        st.caption(
                            "Use this trace ID to find the distributed trace in Tempo"
                        )
            else:
                # Log error response
                logger.error(
                    "Backend returned error",
                    extra={
                        "extra_fields": {
                            "die_type": die_type,
                            "backend_status": response.status_code,
                        }
                    },
                )

                st.error(f"❌ Error: Backend returned status {response.status_code}")
                st.write(response.text)

        except requests.exceptions.Timeout:
            logger.error(
                "Backend request timed out",
                extra={"extra_fields": {"die_type": die_type}},
            )
            st.error("❌ Error: Request timed out")
        except requests.exceptions.ConnectionError:
            logger.error(
                "Failed to connect to backend",
                extra={"extra_fields": {"die_type": die_type}},
            )
            st.error(f"❌ Error: Could not connect to backend at {BACKEND_URL}")
        except Exception as e:
            logger.error(
                f"Unexpected error: {str(e)}",
                extra={"extra_fields": {"die_type": die_type}},
            )
            st.error(f"❌ Error: {str(e)}")

# Show info
with st.sidebar:
    st.header("ℹ️ Info")
    st.write(f"**Backend:** `{BACKEND_URL}`")
    st.write("**Metrics:** Port 8501 `/metrics`")
    st.write("**Tracing:** OpenTelemetry enabled")

    st.header("📊 About")
    st.write("This frontend demonstrates:")
    st.write("- Distributed tracing (W3C Trace Context)")
    st.write("- Prometheus metrics")
    st.write("- Structured JSON logging")
    st.write("- Trace-to-logs correlation")
