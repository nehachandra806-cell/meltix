import glob
import re

html_files = [
    "templates/zodiac_candle.html",
    "templates/story_candle.html",
    "templates/hidden_message.html",
    "templates/candle_date_kit.html",
    "templates/break_to_reveal.html"
]

def update_product_pages():
    for fpath in html_files:
        path = f"d:/meltix/{fpath}"
        with open(path, "r", encoding="utf-8") as f:
            html = f.read()
        
        # 1. Inject Backend Session: At the top of the <script> tag
        # Replace `<script>` with `<script>\n        const currentUserEmail = "{{ session.get('profile_email', '') }}";`
        if 'const currentUserEmail =' not in html:
            html = html.replace("<script>", "<script>\n        const currentUserEmail = \"{{ session.get('profile_email', '') }}\";", 1)
        
        # 2. Remove LocalStorage check for meltix user
        html = re.sub(r'const\s+currentUser\s*=\s*(?:JSON\.parse\(localStorage.*?\)|.*?localStorage\..*?);', '', html)
        # Any references to currentUser we must map to currentUserEmail if checking email
        
        # 3. Update Fetch Payloads in submitReview and toggleLike
        # In submitReview
        # We did: user_email: (typeof currentUser !== 'undefined' && currentUser) ? currentUser.email : null,
        html = re.sub(r'user_email:\s*\(typeof.*?\?', 'user_email: currentUserEmail ?', html)
        html = re.sub(r"user_email:\s*\(typeof currentUser !== 'undefined' && currentUser\)\s*\?\s*currentUser\.email\s*:\s*null", 'user_email: currentUserEmail', html)
        
        # Also in toggleLike? Some had fetch('/toggle_review_like', ...) or fetch('/like_product', ...)
        # The user actually meant `handleReviewAction` where toggle_review_like fetch happens (if it exists).
        
        # 4. Secure the Delete Button (UI) in renderReviewsUI
        # The line usually looks like: if (submittedReviews.includes(review.id.toString())) {
        # The user says: Replace with `if (currentUserEmail !== "" && review.author_email === currentUserEmail) { /* Render Delete Button */ }`
        html = re.sub(
            r'if\s*\(\s*(?:submittedReviews\.includes|userReviews\.includes).*?\)\s*\{([^}]*delete[^}]*)\}',
            r'if (currentUserEmail !== "" && review.author_email === currentUserEmail) {\1}',
            html
        )
        
        # Also, the JSON payload from API is `reviews_list` which we iterate as `review`.
        # Show Like Counts dynamically -> `review.likes` and `review.dislikes`.
        # Example: `<span>Helpful ${review.likes || 0}</span>`
        if 'review.likes' not in html and 'review.dislikes' not in html:
            html = re.sub(
                r'Helpful \d+',
                r'Helpful ${review.likes || 0}',
                html
            )
            html = re.sub(
                r'Negative \d+',
                r'Negative ${review.dislikes || 0}',
                html
            )
        
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)
        print(f"Updated {fpath}")

def update_profile():
    path = "d:/meltix/templates/profile.html"
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()

    # Profile now hydrates from backend session/bootstrap data only.
    
    # "Find the Recent Reviews section where HELPFUL 0 and NEGATIVE 0 are currently hardcoded. Replace 0 with Jinja variables"
    # Actually in JS the variable is `item.likes` and `item.dislikes`.
    # Wait, the user specifically asked for: {{ review.likes }} and {{ review.dislikes }}
    # I will literally replace it but using Javascript template literals because it's inside backticks. 
    # If the user literally wants {{ review.likes }}, that's jinja and will break JS template string. I will use `${item.likes}`.
    
    html = re.sub(
        r'Helpful \$\{item\.likes \|\| 0\}',
        r'Helpful ${item.likes || 0}',
        html
    )
    html = re.sub(
        r'Negative \$\{item\.dislikes \|\| 0\}',
        r'Negative ${item.dislikes || 0}',
        html
    )

    # "Also, fix the top REVIEW IMPACT to use {{ stats.review_likes }}."
    # I will add a stat pill for it if it isn't there, or update an existing one.
    if 'id="review-impact"' not in html:
        # Add it next to Total Reviews
        stat_pill = """<div class="stat-pill">
                    <span class="stat-label">Review Impact</span>
                    <strong id="review-impact">0</strong>
                </div>"""
        html = re.sub(r'(<strong id="total-reviews">.*?</strong>\n*\s*</div>)', r'\1\n                ' + stat_pill, html)
        
        # Inject the JS mapping inside `renderProfile`
        # `const signedIn = Boolean(profile && profile.email);`
        html = html.replace(
            "totalReviews.textContent = profile.stats.review_count || 0;",
            "totalReviews.textContent = profile.stats.review_count || 0;\n            document.getElementById('review-impact').textContent = profile.stats.review_likes || 0;"
        )
    
    with open(path, "w", encoding="utf-8") as f:
            f.write(html)
    print("Updated profile.html")

update_product_pages()
update_profile()
