"""Plain stdlib logging -- no DB table. Job lifecycle transitions and
rejections go through app.domain.server's logger at INFO/WARNING; `job_event`
rows are the queryable, permanent record, logs are for operators tailing
output. configure_logging() is called once from app.main at import time.

Also writes the same records as JSON lines to backend/logs/app.log, purely so
Promtail (observability/promtail/promtail-config.yml) has a file to tail and
ship into Loki -- the stdout handler below is unaffected and stays the primary
way to watch logs when running the app directly."""

import json
import logging
import os
from logging.handlers import RotatingFileHandler

LOG_DIR = os.path.join(os.path.dirname(__file__), "..", "logs")


class _JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload)


def configure_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    # app.database sets echo=True (raw SQL to stdout) independently of this --
    # without this, attaching a root handler here would also surface every
    # query at INFO (under the sqlalchemy.engine.Engine logger specifically,
    # not just sqlalchemy.engine), drowning out the actual lifecycle/rejection
    # log lines this module exists for.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine.Engine").setLevel(logging.WARNING)

    os.makedirs(LOG_DIR, exist_ok=True)
    file_handler = RotatingFileHandler(os.path.join(LOG_DIR, "app.log"), maxBytes=10_000_000, backupCount=3)
    file_handler.setFormatter(_JsonFormatter())
    logging.getLogger().addHandler(file_handler)
