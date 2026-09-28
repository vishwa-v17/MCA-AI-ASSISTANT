from flask import Flask, jsonify, request, render_template
import os
import logging
from flask_wtf.csrf import CSRFProtect, CSRFError
from werkzeug.middleware.proxy_fix import ProxyFix
from app.config import Config
from app.services.db_service import init_db

csrf = CSRFProtect()

def create_app():
    app = Flask(__name__,
                template_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'templates'),
                static_folder=os.path.join(os.path.dirname(os.path.dirname(__file__)), 'static'))

    # Configure upload settings
    app.config['MAX_CONTENT_LENGTH'] = Config.MAX_CONTENT_LENGTH
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

    app.config.from_object(Config)

    # Support reverse proxy (Render / Load balancers)
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1)

    # CSRF Protection
    csrf.init_app(app)

    # Initialize DB
    init_db()

    # Security Headers
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Permissions-Policy'] = 'camera=(), microphone=(), geolocation=()'

        # Robust Content-Security-Policy compatible with required CDNs
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdnjs.cloudflare.com; "
            "font-src 'self' https://fonts.gstatic.com https://cdnjs.cloudflare.com; "
            "img-src 'self' data: blob:; "
            "connect-src 'self'; "
            "frame-ancestors 'self';"
        )
        response.headers['Content-Security-Policy'] = csp

        if request.is_secure or request.headers.get('X-Forwarded-Proto') == 'https':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

        return response

    # Global Error Handlers
    def _is_api_request():
        return (
            request.is_json
            or request.headers.get('X-Requested-With') == 'XMLHttpRequest'
            or request.path.startswith('/api/')
            or request.path == '/chat'
        )

    @app.errorhandler(CSRFError)
    def handle_csrf_error(e):
        if _is_api_request():
            return jsonify({'error': 'CSRF token missing or invalid. Please refresh the page.'}), 400
        return render_template('login.html', error='Session expired or CSRF token invalid. Please log in again.'), 400

    @app.errorhandler(429)
    def handle_ratelimit_error(e):
        msg = 'Rate limit exceeded. Please try again later.'
        if _is_api_request():
            return jsonify({'error': msg}), 429
        return render_template('login.html', error=msg), 429

    @app.errorhandler(404)
    def handle_not_found_error(e):
        if _is_api_request():
            return jsonify({'error': 'Resource not found.'}), 404
        return render_template('login.html', error='Requested page not found.'), 404

    @app.errorhandler(500)
    def handle_server_error(e):
        logging.error("Internal server error: %s", str(e), exc_info=True)
        if _is_api_request():
            return jsonify({'error': 'An internal error occurred. Please try again later.'}), 500
        return render_template('login.html', error='An unexpected error occurred. Please try again later.'), 500

    # Load Blueprints
    from app.routes.auth import auth_bp
    from app.routes.chat import chat_bp
    from app.routes.dashboard import dashboard_bp
    from app.routes.subjects import subjects_bp
    from app.routes.config import config_bp
    from app.routes.upload import upload_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(chat_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(subjects_bp)
    app.register_blueprint(config_bp)
    app.register_blueprint(upload_bp)

    return app
