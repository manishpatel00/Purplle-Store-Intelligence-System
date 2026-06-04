import re

with open("app/models.py", "r") as f:
    content = f.read()

import_pydantic = "\nfrom pydantic import field_validator\n"
if "field_validator" not in content:
    content = content.replace("from sqlmodel import Field, SQLModel", "from pydantic import field_validator\nfrom sqlmodel import Field, SQLModel")

validators = """
    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v: str) -> str:
        if not v.endswith("Z"):
            raise ValueError("Timestamp must be ISO-8601 UTC with Z suffix")
        return v

    @field_validator("confidence")
    @classmethod
    def validate_confidence(cls, v: float) -> float:
        if not (0.0 <= v <= 1.0):
            raise ValueError("Confidence must be between 0.0 and 1.0")
        return v

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v: str) -> str:
        if v not in VALID_EVENT_TYPES:
            raise ValueError(f"Invalid event type: {v}")
        return v

    @field_validator("extra_metadata")
    @classmethod
    def validate_metadata(cls, v: dict) -> dict:
        qd = v.get("queue_depth")
        if qd is not None and isinstance(qd, (int, float)) and qd < 0:
            raise ValueError("queue_depth must be non-negative")
        return v
"""

if "@field_validator" not in content:
    # Insert validators before VALID_EVENT_TYPES
    content = content.replace("# Valid event types", validators + "\n# Valid event types")

with open("app/models.py", "w") as f:
    f.write(content)

print("Added validators to models.py")
