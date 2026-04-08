import os
import glob

templates_dir = r"d:\meltix\templates"
html_files = glob.glob(os.path.join(templates_dir, "*.html"))

for filepath in html_files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # Fix the bad escape
    content = content.replace(r"typeof currentUser !== \'undefined\'", "typeof currentUser !== 'undefined'")

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed backslashes in: {os.path.basename(filepath)}")

