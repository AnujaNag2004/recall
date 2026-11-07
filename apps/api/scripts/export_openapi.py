"""Writes the OpenAPI schema to stdout; the web app generates its types from it."""

import json

from app.main import create_app

print(json.dumps(create_app().openapi(), indent=2))
