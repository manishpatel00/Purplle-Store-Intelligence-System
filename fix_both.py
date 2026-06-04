import re

# Fix UUID validation in models.py
with open("app/models.py", "r") as f:
    models_content = f.read()

uuid_validator = """
    @field_validator("event_id")
    @classmethod
    def validate_event_id(cls, v: str) -> str:
        import uuid
        try:
            uuid.UUID(v)
        except ValueError:
            raise ValueError(f"event_id must be a valid UUID: {v}")
        return v
"""

if "def validate_event_id" not in models_content:
    models_content = models_content.replace('def validate_timestamp', uuid_validator.lstrip() + '\n    @field_validator("timestamp")\n    @classmethod\n    def validate_timestamp')
    with open("app/models.py", "w") as f:
        f.write(models_content)

# Fix event IDs in tests
with open("tests/test_api_schema_validation.py", "r") as f:
    tests_content = f.read()

# Change prefix in test_metrics_zero_purchase_history_valid_response
tests_content = tests_content.replace('f"550e8400-e29b-41d4-a716-44665544000{i}"', 'f"770e8400-e29b-41d4-a716-44665544000{i}"')

with open("tests/test_api_schema_validation.py", "w") as f:
    f.write(tests_content)

print("Fixed UUID and test IDs.")
