"""Structured logging with OpenTelemetry compatibility."""
import json
import logging
import sys
import time
import uuid
from datetime import datetime
from typing import Any, Optional


class StructuredFormatter(logging.Formatter):
    """Formatter that outputs structured JSON logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_entry.update(record.extra_fields)

        return json.dumps(log_entry)


class StructuredLogger(logging.Logger):
    """Logger that supports structured logging with extra fields."""

    def _log(
        self,
        level: int,
        msg: str,
        args: tuple[Any, ...],
        exc_info: Optional[tuple[Any, ...]] = None,
        extra: Optional[dict[str, Any]] = None,
        stack_info: bool = False,
    ) -> None:
        """
        Internal log method with extra fields support.
        
        Args:
            level: Log level.
            msg: Log message.
            args: Message formatting arguments.
            exc_info: Exception info tuple.
            extra: Extra fields to include in log.
            stack_info: Whether to include stack info.
        """
        if extra is None:
            extra = {}

        # Attach extra fields to record
        if "extra_fields" not in extra:
            extra["extra_fields"] = {}

        return super()._log(
            level=level,
            msg=msg,
            args=args,
            exc_info=exc_info,
            extra=extra,
            stack_info=stack_info,
        )

    def info_with_context(
        self, msg: str, **kwargs: Any
    ) -> None:
        """
        Log info with contextual fields.
        
        Args:
            msg: Log message.
            **kwargs: Extra fields to include.
        """
        self.info(msg, extra={"extra_fields": kwargs})

    def error_with_context(
        self, msg: str, **kwargs: Any
    ) -> None:
        """
        Log error with contextual fields.
        
        Args:
            msg: Log message.
            **kwargs: Extra fields to include.
        """
        self.error(msg, extra={"extra_fields": kwargs})

    def debug_with_context(
        self, msg: str, **kwargs: Any
    ) -> None:
        """
        Log debug with contextual fields.
        
        Args:
            msg: Log message.
            **kwargs: Extra fields to include.
        """
        self.debug(msg, extra={"extra_fields": kwargs})


def setup_structured_logging(log_level: str = "INFO") -> None:
    """
    Setup structured logging for the application.
    
    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
    """
    logging.setLoggerClass(StructuredLogger)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Add console handler with structured formatter
    handler = logging.StreamHandler(sys.stdout)
    formatter = StructuredFormatter()
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)


class LogContextManager:
    """Context manager for request logging with trace ID."""

    def __init__(self, logger: logging.Logger, trace_id: Optional[str] = None) -> None:
        """
        Initialize log context.
        
        Args:
            logger: Logger instance.
            trace_id: Optional trace ID (UUID generated if not provided).
        """
        self.logger = logger
        self.trace_id = trace_id or str(uuid.uuid4())
        self.start_time = time.time()

    def __enter__(self) -> "LogContextManager":
        """Enter context."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit context and log summary."""
        duration = time.time() - self.start_time

        if exc_type is not None:
            self.logger.error_with_context(
                f"Operation failed with {exc_type.__name__}",
                trace_id=self.trace_id,
                duration_seconds=duration,
                error=str(exc_val),
            )
        else:
            self.logger.info_with_context(
                "Operation completed",
                trace_id=self.trace_id,
                duration_seconds=duration,
            )
