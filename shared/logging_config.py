import logging
import os
from logging.handlers import RotatingFileHandler


def configure_file_logging() -> None:
    log_file = os.getenv("APP_LOG_FILE")
    if not log_file:
        return

    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )
    )
    logging.getLogger().addHandler(handler)
