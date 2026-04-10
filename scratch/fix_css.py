import re

css_path = 'd:/meltix/static/profile.css'
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

# Fix 1: Reward Progress Fill
old_progress = """.reward-progress-fill {
    width: 0;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--accent-gold), #f2c98a, #fff0d7);
    box-shadow: 0 0 22px rgba(242, 201, 138, 0.34);
    transition: width 0.3s ease;
}"""

new_progress = """.reward-progress-fill {
    width: 0;
    height: 100%;
    border-radius: inherit;
    background: linear-gradient(90deg, var(--accent-gold), #f2c98a, #fff0d7);
    /* Liquid Gold Glow & Inset */
    box-shadow: 0 0 12px rgba(212, 163, 115, 0.6), inset 0 0 5px rgba(255, 255, 255, 0.3);
    transition: width 1.5s cubic-bezier(0.4, 0, 0.2, 1);
}"""

css = css.replace(old_progress, new_progress)

# Fix 2: Ledger List Scroll
old_ledger = """.ledger-list {
    margin-top: 18px;
    display: grid;
    gap: 12px;
}"""

new_ledger = """.ledger-list {
    margin-top: 18px;
    display: grid;
    gap: 12px;
    /* Fading scroll */
    max-height: 250px;
    overflow-y: auto;
    padding-right: 10px;
    -webkit-mask-image: linear-gradient(to bottom, black 85%, transparent 100%);
    mask-image: linear-gradient(to bottom, black 85%, transparent 100%);
}"""

css = css.replace(old_ledger, new_ledger)

# Fix 3: Review List Scroll
# Since review-list is part of a grouped selector, we append standard rules for it.
review_fade = """

/* Fading scroll for reviews */
.review-list {
    max-height: 400px;
    overflow-y: auto;
    padding-right: 10px;
    -webkit-mask-image: linear-gradient(to bottom, black 88%, transparent 100%);
    mask-image: linear-gradient(to bottom, black 88%, transparent 100%);
}
"""
css += review_fade

with open(css_path, 'w', encoding='utf-8') as f:
    f.write(css)

print("CSS updated successfully")
