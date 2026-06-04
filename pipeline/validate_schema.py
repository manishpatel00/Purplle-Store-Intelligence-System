"""
pipeline/validate_schema.py — CLI to validate JSONL events against Pydantic schema
"""

import sys

from pydantic import ValidationError

from app.models import EventCreate


def validate_jsonl(path: str) -> None:
    """Read a JSONL file and validate each line against EventCreate."""
    errors = []
    valid = 0
    total = 0

    try:
        with open(path, encoding="utf-8") as f:
            for i, line in enumerate(f, 1):
                line = line.strip()
                if not line or line.startswith("//") or line.startswith("#"):
                    continue
                total += 1
                try:
                    # Validate JSON structure using Pydantic EventCreate
                    EventCreate.model_validate_json(line)
                    valid += 1
                except ValidationError as e:
                    errors.append({"line": i, "errors": e.errors()})
                except Exception as e:
                    errors.append(
                        {
                            "line": i,
                            "errors": [{"loc": ("json",), "msg": str(e), "type": "value_error"}],
                        }
                    )
    except FileNotFoundError:
        print(f"Error: File '{path}' not found.")
        sys.exit(1)

    print(f"\nSchema Validation Report: {path}")
    print(f"  Total events : {total}")
    print(f"  Valid        : {valid}")
    print(f"  Invalid      : {len(errors)}")

    if errors:
        print("\nFirst 10 validation failures:")
        for err in errors[:10]:
            print(f"  Line {err['line']}:")
            for e in err["errors"]:
                loc = " -> ".join(str(x) for x in e.get("loc", []))
                print(f"    [{loc}] {e.get('msg')}")

        print("\n  ❌ FAILED — fix errors before ingesting")
        sys.exit(1)
    else:
        print("\n  ✅ PASSED — all events match schema")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python3 -m pipeline.validate_schema <path_to_jsonl>")
        sys.exit(1)
    validate_jsonl(sys.argv[1])
