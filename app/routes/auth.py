import re
import uuid
import logging
from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash

from app.services.db_service import get_user_by_username, create_user
from app.services.rate_limiter import user_rate_limiter, get_client_ip
from app.config import Config


auth_bp = Blueprint('auth', __name__)

USERNAME_REGEX = re.compile(r'^[a-zA-Z0-9_\-\.]{3,40}$')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():

    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        client_ip = get_client_ip(request)

        # Rate limiting by IP to prevent brute-force attacks
        if not user_rate_limiter.allow_window(f"login:{client_ip}", Config.AUTH_RATE_LIMIT_PER_MINUTE, 60):
            flash('Too many login attempts. Please wait a minute and try again.', 'error')
            return render_template('login.html'), 429

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html')

        # Limit password input length to prevent hash-DoS
        if len(password) > 128:
            flash('Invalid username or password.', 'error')
            return render_template('login.html')

        user = get_user_by_username(username)

        if user and check_password_hash(user['password_hash'], password):
            # Session fixation protection: clear pre-existing session before populating
            session.clear()
            session['user_id'] = user['id']
            session['username'] = user['username']
            session.permanent = True

            return redirect(url_for('dashboard.index'))
        else:
            logging.warning("Failed login attempt for username: %s from IP: %s", username[:40], client_ip)
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():

    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        client_ip = get_client_ip(request)

        # Rate limiting by IP to prevent mass registration
        if not user_rate_limiter.allow_window(f"register:{client_ip}", Config.REGISTER_RATE_LIMIT_PER_HOUR, 3600):
            flash('Too many accounts created from this network. Please try again later.', 'error')
            return render_template('register.html'), 429

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('register.html')

        if not USERNAME_REGEX.match(username):
            flash('Username must be 3-40 characters and contain only letters, numbers, underscores, dashes, or dots.', 'error')
            return render_template('register.html')

        if len(password) < 8:
            flash('Password must be at least 8 characters long.', 'error')
            return render_template('register.html')

        if len(password) > 128:
            flash('Password must not exceed 128 characters.', 'error')
            return render_template('register.html')

        existing_user = get_user_by_username(username)

        if existing_user:
            flash('Username already exists. Please choose a different one.', 'error')
            return render_template('register.html')

        user_id = str(uuid.uuid4())
        password_hash = generate_password_hash(password)

        create_user(
            user_id,
            username,
            password_hash
        )

        flash('Account created successfully. Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    session.clear()
    response = redirect(url_for('auth.login'))
    # Explicitly expire session cookie
    response.delete_cookie(Config.SECRET_KEY)
    return response

