"""Writes the FastAPI app's current OpenAPI schema to frontend/openapi.json,
the input openapi-typescript codegen runs against (see frontend/package.json's
generate:api script). Doesn't need a running server -- app.openapi() builds the
schema directly from the route definitions. Run via the root package.json's
generate:api script, which puts backend/ on PYTHONPATH.
"""

import json
from pathlib import Path

from app.main import app

OUTPUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "openapi.json"

OUTPUT_PATH.write_text(json.dumps(app.openapi(), indent=2))
print(f"wrote {OUTPUT_PATH}")
