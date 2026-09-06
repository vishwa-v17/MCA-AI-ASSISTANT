from flask import Blueprint, render_template, redirect, url_for, session
from app.services.db_service import get_user_by_username, get_sessions

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('auth.login'))
        
    # We pass the username to the template
    username = session.get('username', 'Student')
    return render_template('index.html', username=username)

