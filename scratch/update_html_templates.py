import os
import glob
import re

templates_dir = r"d:\meltix\templates"
html_files = glob.glob(os.path.join(templates_dir, "*.html"))

for filepath in html_files:
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content
    
    # Update submit_review payloads
    # It usually looks like:
    #                     product_id: activeProductId,
    #                     user_name: name,
    #                     review_text: text,
    #                     rating: rating
    
    # We want to insert `user_email: (typeof currentUser !== 'undefined' && currentUser) ? currentUser.email : null,`
    # Let's match `user_name: name,` and replace it
    content = re.sub(
        r'(user_name:\s*name,\s*)',
        r'\1user_email: (typeof currentUser !== \'undefined\' && currentUser) ? currentUser.email : null,\n                        ',
        content
    )

    # Some templates might not have `toggle_review_like` fetch call at all, some might have it.
    # The user said: "pass the user_email in the fetch payloads for both /submit_review and /toggle_review_like."
    # Wait, earlier I saw in `zodiac_candle.html` `toggle_review_like` was absent? 
    # Let's check if `/toggle_review_like` is present and update it.
    
    # Let's match `action:\s*isLiked\s*\?\s*'like'\s*:\s*'unlike'` or similar inside `toggle_review_like`.
    # Wait, the toggle review like in Python app.py looks for `review_id`, `user_name`, `action`.
    # Let's look for `review_id:\s*reviewId,`
    content = re.sub(
        r'(review_id:\s*[a-zA-Z0-9]+,\s*)',
        r'\1user_email: (typeof currentUser !== \'undefined\' && currentUser) ? currentUser.email : null,\n                                ',
        content
    )
    
    # Let's also check if the user asked me to add the fetch call for toggle_review_like if it was missing?
    # No, they just said "update the frontend HTML templates to pass the user_email in the fetch payloads for both /submit_review and /toggle_review_like."
    # If the fetch is there, this regex will catch it if it passes `review_id`. Wait, does it pass `review_id`?
    # If the user's templates do send `fetch('/toggle_review_like'`, they must send `review_id: ...`.

    if content != original_content:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Updated: {os.path.basename(filepath)}")
    else:
        print(f"No changes needed: {os.path.basename(filepath)}")

