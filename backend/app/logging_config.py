"""Plain stdlib logging -- no DB table. Job lifecycle transitions and
rejections go through app.domain.server's logger at INFO/WARNING; `job_event`
rows are the queryable, permanent record, logs are for operators tailing
output. configure_logging() is called once from app.main at import time."""

import logging


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
