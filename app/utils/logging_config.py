import logging
import sys
import structlog
from app.config import settings

def configure_logging():
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if settings.ENV == "development":
        # Pretty printing for dev
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer()
        ]
    else:
        # JSON for production
        processors = shared_processors + [
            structlog.processors.dict_tracebacks,
            structlog.processors.JSONRenderer(),
        ]

    structlog.configure(
        processors=processors,
        logger_factory=structlog.PrintLoggerFactory(),
        wrapper_class=structlog.make_filtering_bound_logger(logging.getLevelName(settings.LOG_LEVEL)),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging to intercept everything
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=settings.LOG_LEVEL,
    )
    
    # Silence noisy libs
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)

logger = structlog.get_logger()
