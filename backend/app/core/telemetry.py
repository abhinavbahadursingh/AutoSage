"""Telemetry, logging, and OpenTelemetry helpers."""
import logging

logging.basicConfig(
    level=logging.INFO,
    format='{"timestamp": "%(asctime)s", "level": "%(levelname)s", "module": "%(name)s", "message": "%(message)s"}'
)

logger = logging.getLogger("autosage")
