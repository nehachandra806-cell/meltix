import os
import re

app_py_path = r'd:\meltix\app.py'

with open(app_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

# Fix serialize_profile
old_all_reviews = "    all_reviews = Review.query.filter_by(user_name=profile_record.display_name).order_by(Review.created_at.desc()).all()"
new_all_reviews = "    all_reviews = Review.query.filter_by(user_id=profile_record.id).order_by(Review.created_at.desc()).all()"
content = content.replace(old_all_reviews, new_all_reviews)

# Fix get_reviews
old_get_reviews_loop = """    for r in reviews:
        # Is review ke total 'like' count karo
        likes_count = ReviewLike.query.filter_by(review_id=r.id, action_type='like').count()
        
        reviews_list.append({
            'id': r.id, # 🔴 FIX: ID bhejna zaroori hai Javascript ko delete/like ke liye
            'user_name': r.user_name,
            'review_text': r.review_text,
            'rating': r.rating,
            'date': r.created_at.strftime("%d %b %Y"),
            'likes': likes_count
        })"""

new_get_reviews_loop = """    for r in reviews:
        # Is review ke total 'like' count karo
        likes_count = ReviewLike.query.filter_by(review_id=r.id, action_type='like').count()
        
        author = db.session.get(UserAccount, r.user_id)
        
        reviews_list.append({
            'id': r.id, # 🔴 FIX: ID bhejna zaroori hai Javascript ko delete/like ke liye
            'user_name': r.user_name,
            'author_email': author.email if author else "",
            'review_text': r.review_text,
            'rating': r.rating,
            'date': r.created_at.strftime("%d %b %Y"),
            'likes': likes_count
        })"""

content = content.replace(old_get_reviews_loop, new_get_reviews_loop)

# Fix delete route to verify user_id. We're keeping it DELETE but parsing JSON OR using POST. The user said: "change method from DELETE to POST, or use request.get_json() carefully". We'll use POST.
old_delete_route = """@app.route('/delete_review/<int:review_id>', methods=['DELETE'])
def delete_review_route(review_id):
    try:
        review = db.session.get(Review, review_id)
        if review:
            db.session.delete(review) # Cascade ki wajah se likes automatically delete ho jayenge
            db.session.commit()
            return jsonify({"status": "success"}), 200
        return jsonify({"status": "error", "message": "Review not found"}), 404
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500"""

new_delete_route = """@app.route('/delete_review/<int:review_id>', methods=['POST', 'DELETE'])
def delete_review_route(review_id):
    try:
        data = request.get_json() or {}
        user_email = data.get('user_email')
        
        user_account = None
        if user_email:
            user_account = UserAccount.query.filter_by(email=user_email).first()
        elif 'profile_email' in session:
            user_account = UserAccount.query.filter_by(email=session['profile_email']).first()
            
        if not user_account:
            return jsonify({'status': 'error', 'message': 'Login required'}), 401
            
        review = db.session.get(Review, review_id)
        if not review:
            return jsonify({"status": "error", "message": "Review not found"}), 404
            
        if review.user_id != user_account.id:
            return jsonify({"status": "error", "message": "Unauthorized"}), 403
            
        db.session.delete(review) # Cascade deletes likes
        db.session.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500"""

content = content.replace(old_delete_route, new_delete_route)

with open(app_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Backend app.py updated via python script.")
