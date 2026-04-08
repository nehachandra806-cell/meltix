import re
import glob

html_files = [
    "templates/zodiac_candle.html",
    "templates/story_candle.html",
    "templates/hidden_message.html",
    "templates/candle_date_kit.html",
    "templates/break_to_reveal.html"
]

for fpath in html_files:
    path = f"d:/meltix/{fpath}"
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # Apply Delete button conditionally
    # We replace: <button class="delete-review-btn" onclick="deleteReview(${r.id})" title="Delete Review">🗑️</button>
    old_btn = r'<button class="delete-review-btn" onclick="deleteReview\(\$\{r\.id\}\)" title="Delete Review">🗑️</button>'
    new_btn = r"""${ (currentUserEmail !== "" && r.author_email === currentUserEmail) ? `<button class="delete-review-btn" onclick="deleteReview(${r.id})" title="Delete Review">🗑️</button>` : '' }"""
    html = re.sub(old_btn, new_btn, html)

    # Apply delete payload POST update
    old_delete_fetch = r"fetch\(`/delete_review/\$\{reviewId\}`,\s*\{\s*method:\s*'DELETE'\s*\}\)"
    new_delete_fetch = r"fetch(`/delete_review/${reviewId}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({user_email: currentUserEmail}) })"
    html = re.sub(old_delete_fetch, new_delete_fetch, html)
    
    # Just in case there are single quotes:
    old_delete_fetch2 = r"fetch\('/delete_review/' \+ reviewId,\s*\{\s*method:\s*'DELETE'\s*\}\)"
    new_delete_fetch2 = r"fetch('/delete_review/' + reviewId, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({user_email: currentUserEmail}) })"
    html = re.sub(old_delete_fetch2, new_delete_fetch2, html)

    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    
    print(f"Updated {path}")
