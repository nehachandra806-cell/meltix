@app.route('/')
def home(
@app.route('/shop')
def shop(
@app.route('/hidden-message')
def hidden_message(
@app.route('/story-candle')
def story_candle(
@app.route('/zodiac-candle')
def zodiac_candle(
@app.route('/break-to-reveal')
def break_to_reveal(
@app.route('/candle-date-kit')
def candle_date_kit(
@app.route('/about-us')
def about_us(
@app.route('/contact-us')
def contact_us(
@app.route('/craft-studio')
def craft_studio(
@app.route('/head_to')
def head_to(
@app.route('/suggestions')
def suggestions(
@app.route('/gift_sets')
def gift_sets(
@app.route('/feedback')
def feedback(
@app.route('/bug-report')
def bug_report(
@app.route('/profile')
def profile(
@app.route('/like_product', methods=['POST'])
def like_product(
@app.route('/submit_review', methods=['POST'])
def submit_review(
@app.route('/get_reviews/<int:product_id>', methods=['GET'])
def get_reviews(
@app.route('/delete_review/<int:review_id>', methods=['DELETE'])
def delete_review_route(
@app.route('/toggle_review_like', methods=['POST'])
def toggle_review_like(
@app.route('/toggle_wishlist', methods=['POST'])
def toggle_wishlist(
@app.route('/api/profile/bootstrap', methods=['POST'])
def profile_bootstrap(
@app.route('/api/profile/avatar', methods=['POST'])
def update_profile_avatar(
@app.route('/api/profile/address', methods=['POST'])
def save_profile_address(
@app.route('/api/profile/scent-persona', methods=['POST'])
def save_scent_persona(