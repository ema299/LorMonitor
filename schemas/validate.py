"""JSON Schema validator for API contracts."""
import json
from pathlib import Path

try:
    import jsonschema
except ImportError:
    jsonschema = None

SCHEMA_DIR = Path(__file__).parent


def load_schema(name: str) -> dict:
    path = SCHEMA_DIR / f"{name}.schema.json"
    with open(path) as f:
        return json.load(f)


def validate(data: dict, schema_name: str) -> list[str]:
    """Validate data against a named schema. Returns list of errors (empty = valid)."""
    if jsonschema is None:
        return ["jsonschema package not installed"]

    schema = load_schema(schema_name)
    errors = []
    for error in jsonschema.Draft202012Validator(schema).iter_errors(data):
        errors.append(f"{error.json_path}: {error.message}")
    return errors


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 3:
        print("Usage: python -m schemas.validate <schema_name> <json_file>")
        sys.exit(1)
    schema_name = sys.argv[1]
    with open(sys.argv[2]) as f:
        data = json.load(f)
    errors = validate(data, schema_name)
    if errors:
        for e in errors:
            print(f"  FAIL: {e}")
        sys.exit(1)
    print("OK")
