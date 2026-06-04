with open("tests/test_group_entry_detection.py", "r") as f:
    content = f.read()

content = content.replace(
    'metadata={"queue_depth": queue_tracker.join("STORE_BLR_002", "BILLING")}',
    'queue_depth=queue_tracker.join("STORE_BLR_002", "BILLING")'
)

with open("tests/test_group_entry_detection.py", "w") as f:
    f.write(content)
