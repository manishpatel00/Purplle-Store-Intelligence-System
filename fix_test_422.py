with open("tests/test_api_schema_validation.py", "r") as f:
    content = f.read()

content = content.replace("assert response.status_code == 422", "assert response.status_code == 400")

with open("tests/test_api_schema_validation.py", "w") as f:
    f.write(content)
print("Restored 400 assertions.")
