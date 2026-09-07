from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import uuid

from app.services.db_service import get_user_by_username, create_user


auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():

    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('login.html')

        user = get_user_by_username(username)

        if user and check_password_hash(user['password_hash'], password):

            session['user_id'] = user['id']
            session['username'] = user['username']

            return redirect(url_for('dashboard.index'))

        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():

    if 'user_id' in session:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':

        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Username and password are required.', 'error')
            return render_template('register.html')

        existing_user = get_user_by_username(username)

        if existing_user:
            flash(
                'Username already exists. Please choose a different one.',
                'error'
            )
            return render_template('register.html')

        user_id = str(uuid.uuid4())

        password_hash = generate_password_hash(password)

        create_user(
            user_id,
            username,
            password_hash
        )

        flash('Account created successfully.', 'success')

        return redirect(url_for('auth.login'))

    return render_template('register.html')


@auth_bp.route('/logout')
def logout():

    session.clear()

    return redirect(url_for('auth.login'))
