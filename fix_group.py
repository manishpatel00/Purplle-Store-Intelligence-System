with open("tests/test_group_entry_detection.py", "r") as f:
    content = f.read()

# Make base_time naive
content = content.replace('datetime.fromisoformat("2026-04-10T14:20:00Z")', 'datetime.fromisoformat("2026-04-10T14:20:00")')
content = content.replace('datetime.fromisoformat("2026-04-10T14:25:00Z")', 'datetime.fromisoformat("2026-04-10T14:25:00")')

# Fix extra_metadata back to metadata in test_group_entry_billing_queue_join_ordering
content = content.replace('extra_metadata={"queue_depth"', 'metadata={"queue_depth"')

with open("tests/test_group_entry_detection.py", "w") as f:
    f.write(content)
