import os
import re

app_py_path = r'd:\meltix\app.py'

with open(app_py_path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update Review Model
review_old = '''class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False) # Ye batayega kis candle ka review hai
    user_name = db.Column(db.String(100), nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1 se 5 tak star rating
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Review ka time

    # 🔴 STRICT RULE: 1 User = 1 Review per product
    __table_args__ = (db.UniqueConstraint('user_name', 'product_id', name='unique_user_review'),)'''

review_new = '''class Review(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, nullable=False) # Ye batayega kis candle ka review hai
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    review_text = db.Column(db.Text, nullable=False)
    rating = db.Column(db.Integer, nullable=False) # 1 se 5 tak star rating
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Review ka time

    # 🔴 STRICT RULE: 1 User = 1 Review per product
    __table_args__ = (db.UniqueConstraint('user_id', 'product_id', name='unique_user_review'),)'''

content = content.replace(review_old, review_new)

# 2. Update ReviewLike Model
review_like_old = '''class ReviewLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    action_type = db.Column(db.String(10), nullable=False) # 'like' ya 'dislike'

    # STRICT RULE: Ek review pe ek banda ek hi baar like/dislike save kar sake
    __table_args__ = (db.UniqueConstraint('review_id', 'user_name', name='unique_user_review_like'),)'''

review_like_new = '''class ReviewLike(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    review_id = db.Column(db.Integer, db.ForeignKey('review.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user_account.id'), nullable=False)
    user_name = db.Column(db.String(100), nullable=False)
    action_type = db.Column(db.String(10), nullable=False) # 'like' ya 'dislike'

    # STRICT RULE: Ek review pe ek banda ek hi baar like/dislike save kar sake
    __table_args__ = (db.UniqueConstraint('review_id', 'user_id', name='unique_user_review_like'),)'''

content = content.replace(review_like_old, review_like_new)

# 3. Replace UserProfile and UserAddress
user_profile_old = '''class UserProfile(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False, default='Guest')
    avatar_filename = db.Column(db.String(50), nullable=False, default='')
    glow_points = db.Column(db.Integer, nullable=False, default=250)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f"UserProfile('{self.email}', Avatar: {self.avatar_filename})"


# 🔴 NAYA TABLE: Saved Products (Wishlist / Buy Later)
class UserAddress(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    phone_number = db.Column(db.String(25), nullable=False, default='')
    shipping_name = db.Column(db.String(120), nullable=False, default='')
    shipping_line1 = db.Column(db.String(160), nullable=False, default='')
    shipping_line2 = db.Column(db.String(160), nullable=False, default='')
    shipping_city = db.Column(db.String(80), nullable=False, default='')
    shipping_state = db.Column(db.String(80), nullable=False, default='')
    shipping_postal_code = db.Column(db.String(20), nullable=False, default='')
    shipping_country = db.Column(db.String(60), nullable=False, default='India')
    billing_same_as_shipping = db.Column(db.Boolean, nullable=False, default=True)
    billing_name = db.Column(db.String(120), nullable=False, default='')
    billing_line1 = db.Column(db.String(160), nullable=False, default='')
    billing_line2 = db.Column(db.String(160), nullable=False, default='')
    billing_city = db.Column(db.String(80), nullable=False, default='')
    billing_state = db.Column(db.String(80), nullable=False, default='')
    billing_postal_code = db.Column(db.String(20), nullable=False, default='')
    billing_country = db.Column(db.String(60), nullable=False, default='India')
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)'''

user_account_new = '''class UserAccount(db.Model):
    __tablename__ = 'user_account'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    display_name = db.Column(db.String(120), nullable=False, default='Guest')
    avatar_filename = db.Column(db.String(50), nullable=False, default='')
    glow_points = db.Column(db.Integer, nullable=False, default=250)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    phone = db.Column(db.String(25), nullable=False, default='')
    shipping_name = db.Column(db.String(120), nullable=False, default='')
    shipping_line1 = db.Column(db.String(160), nullable=False, default='')
    shipping_line2 = db.Column(db.String(160), nullable=False, default='')
    shipping_city = db.Column(db.String(80), nullable=False, default='')
    shipping_state = db.Column(db.String(80), nullable=False, default='')
    shipping_postal_code = db.Column(db.String(20), nullable=False, default='')
    shipping_country = db.Column(db.String(60), nullable=False, default='India')

    billing_same_as_shipping = db.Column(db.Boolean, nullable=False, default=True)
    billing_name = db.Column(db.String(120), nullable=False, default='')
    billing_line1 = db.Column(db.String(160), nullable=False, default='')
    billing_line2 = db.Column(db.String(160), nullable=False, default='')
    billing_city = db.Column(db.String(80), nullable=False, default='')
    billing_state = db.Column(db.String(80), nullable=False, default='')
    billing_postal_code = db.Column(db.String(20), nullable=False, default='')
    billing_country = db.Column(db.String(60), nullable=False, default='India')

    reviews = db.relationship('Review', backref='author', lazy='dynamic')

    def __repr__(self):
        return f"UserAccount('{self.email}', Avatar: {self.avatar_filename})"'''

content = content.replace(user_profile_old, user_account_new)

# 4. Replace serialize_address
serialize_address_old = '''def serialize_address(address_record):
    if not address_record:
        return {
            "phone_number": "",
            "shipping": {
                "name": "",
                "line1": "",
                "line2": "",
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "India",
            },
            "billing_same_as_shipping": True,
            "billing": {
                "name": "",
                "line1": "",
                "line2": "",
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "India",
            },
        }

    return {
        "phone_number": address_record.phone_number,
        "shipping": {
            "name": address_record.shipping_name,
            "line1": address_record.shipping_line1,
            "line2": address_record.shipping_line2,
            "city": address_record.shipping_city,
            "state": address_record.shipping_state,
            "postal_code": address_record.shipping_postal_code,
            "country": address_record.shipping_country,
        },
        "billing_same_as_shipping": address_record.billing_same_as_shipping,
        "billing": {
            "name": address_record.billing_name,
            "line1": address_record.billing_line1,
            "line2": address_record.billing_line2,
            "city": address_record.billing_city,
            "state": address_record.billing_state,
            "postal_code": address_record.billing_postal_code,
            "country": address_record.billing_country,
        },
    }'''

serialize_address_new = '''def serialize_address(address_record):
    if not address_record:
        return {
            "phone_number": "",
            "shipping": {
                "name": "",
                "line1": "",
                "line2": "",
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "India",
            },
            "billing_same_as_shipping": True,
            "billing": {
                "name": "",
                "line1": "",
                "line2": "",
                "city": "",
                "state": "",
                "postal_code": "",
                "country": "India",
            },
        }

    return {
        "phone_number": address_record.phone,
        "shipping": {
            "name": address_record.shipping_name,
            "line1": address_record.shipping_line1,
            "line2": address_record.shipping_line2,
            "city": address_record.shipping_city,
            "state": address_record.shipping_state,
            "postal_code": address_record.shipping_postal_code,
            "country": address_record.shipping_country,
        },
        "billing_same_as_shipping": address_record.billing_same_as_shipping,
        "billing": {
            "name": address_record.billing_name,
            "line1": address_record.billing_line1,
            "line2": address_record.billing_line2,
            "city": address_record.billing_city,
            "state": address_record.billing_state,
            "postal_code": address_record.billing_postal_code,
            "country": address_record.billing_country,
        },
    }'''
content = content.replace(serialize_address_old, serialize_address_new)

# 5. Replace get_or_create_profile and address
get_create_old = '''def get_or_create_profile(email, display_name=None):
    normalized_email = (email or '').strip().lower()
    readable_name = (display_name or '').strip() or normalized_email.split('@')[0] or 'Guest'

    profile_record = UserProfile.query.filter_by(email=normalized_email).first()
    if not profile_record:
        profile_record = UserProfile(
            email=normalized_email,
            display_name=readable_name,
            avatar_filename=''
        )
        db.session.add(profile_record)
    else:
        profile_record.display_name = readable_name or profile_record.display_name

    return profile_record


def get_or_create_address(user_email):
    address_record = UserAddress.query.filter_by(user_email=user_email).first()
    if not address_record:
        address_record = UserAddress(user_email=user_email)
        db.session.add(address_record)
    return address_record'''

get_create_new = '''def get_or_create_profile(email, display_name=None):
    normalized_email = (email or '').strip().lower()
    readable_name = (display_name or '').strip() or normalized_email.split('@')[0] or 'Guest'

    profile_record = UserAccount.query.filter_by(email=normalized_email).first()
    if not profile_record:
        profile_record = UserAccount(
            email=normalized_email,
            display_name=readable_name,
            avatar_filename=''
        )
        db.session.add(profile_record)
    else:
        if readable_name and readable_name != 'Guest':
            profile_record.display_name = readable_name

    return profile_record'''
content = content.replace(get_create_old, get_create_new)

# 6. Replace serialize_profile address fetching
content = content.replace("address_record = UserAddress.query.filter_by(user_email=profile_record.email).first()\n    address_book = serialize_address(address_record)", "address_book = serialize_address(profile_record)")

# 7. Replace submit_review
submit_review_old = '''@app.route('/submit_review', methods=['POST'])
def submit_review():
    data = request.get_json()
    new_review = Review(
        product_id=int(data.get('product_id')),
        user_name=data.get('user_name'),
        review_text=data.get('review_text'),
        rating=int(data.get('rating'))
    )
    
    try:
        db.session.add(new_review)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Review posted successfully!'}), 200
    except IntegrityError:
        # Postgres rule block karega agar user pehle hi review de chuka hai
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Aap already review de chuke hain!'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500'''

submit_review_new = '''@app.route('/submit_review', methods=['POST'])
def submit_review():
    data = request.get_json()
    try:
        user_email = data.get('user_email')
        
        user_account = None
        if user_email:
            user_account = UserAccount.query.filter_by(email=user_email).first()
        elif 'profile_email' in session:
            user_account = UserAccount.query.filter_by(email=session['profile_email']).first()
            
        if not user_account:
            return jsonify({'success': False, 'message': 'Login required to post a review'}), 401

        new_review = Review(
            product_id=int(data.get('product_id')),
            user_id=user_account.id,
            user_name=data.get('user_name') or user_account.display_name,
            review_text=data.get('review_text'),
            rating=int(data.get('rating'))
        )
        db.session.add(new_review)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Review posted successfully!'}), 200
    except IntegrityError:
        # Postgres rule block karega agar user pehle hi review de chuka hai
        db.session.rollback()
        return jsonify({'success': False, 'message': 'Aap already review de chuke hain!'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': str(e)}), 500'''

content = content.replace(submit_review_old, submit_review_new)

# 8. Replace toggle_review_like
toggle_like_old = '''@app.route('/toggle_review_like', methods=['POST'])
def toggle_review_like():
    data = request.get_json()
    review_id = data.get('review_id')
    user_name = data.get('user_name')
    action = data.get('action')

    try:
        # Check karo agar user ne pehle se koi action liya hai
        existing_action = ReviewLike.query.filter_by(review_id=review_id, user_name=user_name).first()

        if existing_action:
            existing_action.action_type = action # Update kar do (like -> dislike ya vice versa)
        else:
            new_action = ReviewLike(review_id=review_id, user_name=user_name, action_type=action) # Naya banao
            db.session.add(new_action)

        db.session.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500'''

toggle_like_new = '''@app.route('/toggle_review_like', methods=['POST'])
def toggle_review_like():
    data = request.get_json()
    review_id = data.get('review_id')
    user_name = data.get('user_name')
    user_email = data.get('user_email')
    action = data.get('action')

    try:
        user_account = None
        if user_email:
            user_account = UserAccount.query.filter_by(email=user_email).first()
        elif 'profile_email' in session:
            user_account = UserAccount.query.filter_by(email=session['profile_email']).first()
            
        if not user_account:
            return jsonify({'status': 'error', 'message': 'Login required'}), 401
            
        # Check karo agar user ne pehle se koi action liya hai
        existing_action = ReviewLike.query.filter_by(review_id=review_id, user_id=user_account.id).first()

        if existing_action:
            if existing_action.action_type == action:
                db.session.delete(existing_action)
            else:
                existing_action.action_type = action # Update kar do (like -> dislike ya vice versa)
        else:
            new_action = ReviewLike(review_id=review_id, user_id=user_account.id, user_name=user_name or user_account.display_name, action_type=action) # Naya banao
            db.session.add(new_action)

        db.session.commit()
        return jsonify({"status": "success"}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({"status": "error", "message": str(e)}), 500'''

content = content.replace(toggle_like_old, toggle_like_new)

# 9. Replace save_profile_address
save_address_old = '''@app.route('/api/profile/address', methods=['POST'])
def save_profile_address():
    data = request.get_json() or {}
    email = (data.get('email') or session.get('profile_email') or '').strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Sign in required"}), 401

    try:
        address_record = get_or_create_address(email)
        shipping = data.get('shipping') or {}
        billing = data.get('billing') or {}
        billing_same_as_shipping = bool(data.get('billing_same_as_shipping', True))

        address_record.phone_number = (data.get('phone_number') or '').strip()'''

save_address_new = '''@app.route('/api/profile/address', methods=['POST'])
def save_profile_address():
    data = request.get_json() or {}
    email = (data.get('email') or session.get('profile_email') or '').strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Sign in required"}), 401

    try:
        address_record = UserAccount.query.filter_by(email=email).first()
        if not address_record:
            return jsonify({"success": False, "message": "User not found"}), 404
            
        shipping = data.get('shipping') or {}
        billing = data.get('billing') or {}
        billing_same_as_shipping = bool(data.get('billing_same_as_shipping', True))

        address_record.phone = (data.get('phone_number') or '').strip()'''

content = content.replace(save_address_old, save_address_new)

with open(app_py_path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated app.py successfully")
