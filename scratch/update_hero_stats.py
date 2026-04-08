import re

path = r'd:\meltix\templates\profile.html'
with open(path, 'r', encoding='utf-8') as f:
    html = f.read()

# 1. Replace the HTML block
old_stats_block = r"""<div class="hero-stats">
                <div class="stat-pill">
                    <span class="stat-label">Total Reviews</span>
                    <strong id="total-reviews">0</strong>
                </div>
                <div class="stat-pill">
                    <span class="stat-label">Review Impact</span>
                    <strong id="review-impact">{{ stats.review_likes or 0 }}</strong>
                </div>
                <div class="stat-pill">
                    <span class="stat-label">Orders in Progress</span>
                    <strong id="orders-in-progress">0</strong>
                </div>
                <div class="stat-pill">
                    <span class="stat-label">Total Spent</span>
                    <strong id="total-spent">INR 0</strong>
                </div>
                <div class="stat-pill">
                    <span class="stat-label">Saved Candles</span>
                    <strong id="wishlist-count">0</strong>
                </div>
            </div>"""

old_stats_block_fallback = r"""<div class="hero-stats">
                <div class="stat-pill">
                    <span class="stat-label">Total Reviews</span>
                    <strong id="total-reviews">0</strong>
                </div>
                <div class="stat-pill">
                    <span class="stat-label">Orders in Progress</span>
                    <strong id="orders-in-progress">0</strong>
                </div>
                <div class="stat-pill">
                    <span class="stat-label">Total Spent</span>
                    <strong id="total-spent">INR 0</strong>
                </div>
                <div class="stat-pill">
                    <span class="stat-label">Saved Candles</span>
                    <strong id="wishlist-count">0</strong>
                </div>
            </div>"""

new_stats_block = """<div class="hero-stats" style="display: flex; justify-content: center; gap: 16px; flex-wrap: wrap;">
                <div class="stat-pill" style="flex: 1 1 30%; max-width: 180px;">
                    <span class="stat-label">Member Since</span>
                    <strong id="hero-member-since">Today</strong>
                </div>
                <div class="stat-pill" style="flex: 1 1 30%; max-width: 180px;">
                    <span class="stat-label">Orders in Progress</span>
                    <strong id="orders-in-progress">0</strong>
                </div>
                <div class="stat-pill" style="flex: 1 1 30%; max-width: 180px;">
                    <span class="stat-label">Total Spent</span>
                    <strong id="total-spent">INR 0</strong>
                </div>
            </div>"""

if '<div class="stat-pill">\n                    <span class="stat-label">Review Impact</span>' in html:
    html = re.sub(r'<div class="hero-stats">.*?wishlist-count.*?</div>\s*</div>', new_stats_block, html, flags=re.DOTALL)
else:
    html = re.sub(r'<div class="hero-stats">.*?wishlist-count.*?</div>\s*</div>', new_stats_block, html, flags=re.DOTALL)


# 2. Update the JS variable declarations
html = re.sub(r"const totalReviews = document.getElementById\('total-reviews'\);.*?\n", "", html)
html = re.sub(r"const wishlistCount = document.getElementById\('wishlist-count'\);.*?\n", "", html)
# We will inject heroMemberSince where ordersInProgress is declared
html = html.replace("const ordersInProgress = document.getElementById('orders-in-progress');",
                    "const ordersInProgress = document.getElementById('orders-in-progress');\n        const heroMemberSince = document.getElementById('hero-member-since');")

# 3. Update the guest fallback renders in `renderGuestProfile`
html = re.sub(r"totalReviews\.textContent = '0';.*?\n", "", html)
html = re.sub(r"wishlistCount\.textContent = '0';.*?\n", "", html)
html = html.replace("ordersInProgress.textContent = '0';", 
                    "heroMemberSince.textContent = 'Today';\n            ordersInProgress.textContent = '0';")

# 4. Update the profile renders in `renderProfile`
html = re.sub(r"totalReviews\.textContent = profile\.stats\.review_count \|\| 0;.*?\n", "", html)
html = re.sub(r"document\.getElementById\('review-impact'\)\.textContent = profile\.stats\.review_likes \|\| 0;.*?\n", "", html)
html = re.sub(r"wishlistCount\.textContent = profile\.stats\.wishlist_count \|\| 0;.*?\n", "", html)
html = html.replace("ordersInProgress.textContent = profile.stats.orders_in_progress || 0;", 
                    "heroMemberSince.textContent = profile.member_since || 'Today';\n            ordersInProgress.textContent = profile.stats.orders_in_progress || 0;")

with open(path, 'w', encoding='utf-8') as f:
    f.write(html)
print("Updated profile.html")
