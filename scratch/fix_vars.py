import re

py_path = 'd:/meltix/app.py'
with open(py_path, 'r', encoding='utf-8') as f:
    py_content = f.read()

# Fix bootstrap extraction
old_b = "    google_picture_url = (data.get('picture') or '').strip()"
new_b = "    google_picture_url = data.get('google_picture_url') or data.get('picture') or ''"

py_content = py_content.replace(old_b, new_b)

with open(py_path, 'w', encoding='utf-8') as f:
    f.write(py_content)

print("Variables replaced")
