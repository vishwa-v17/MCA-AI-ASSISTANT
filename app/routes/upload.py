from flask import Blueprint, request, jsonify, flash, redirect, url_for, current_app, session, render_template
import os
import uuid
import imghdr
import io
import zipfile
import xml.etree.ElementTree as ET
from werkzeug.utils import secure_filename
from app.config import Config

upload_bp = Blueprint('upload', __name__)

DANGEROUS_EXTENSIONS = {
    'exe', 'bat', 'cmd', 'js', 'py', 'php', 'sh', 'html', 'htm',
    'svg', 'vbs', 'ps1', 'jar', 'msi', 'dll', 'com', 'scr', 'vbe', 'wsf'
}

def _validate_and_save_file(file_storage):
    """
    Validates uploaded file size, extension, and deep magic-byte / file signature.
    Returns: (is_valid: bool, error_message: str, unique_name: str, extracted_text: str)
    """
    filename = file_storage.filename
    if not filename:
        return False, 'No file selected.', None, None

    # Check file size (10 MB limit)
    file_storage.seek(0, os.SEEK_END)
    size = file_storage.tell()
    file_storage.seek(0)
    
    if size > Config.MAX_CONTENT_LENGTH:
        return False, 'File size must not exceed 10 MB.', None, None
    if size == 0:
        return False, 'The selected file is empty.', None, None

    # Extension validation
    ext = os.path.splitext(filename)[1].lower().lstrip('.')
    if ext in DANGEROUS_EXTENSIONS or ext not in Config.ALLOWED_EXTENSIONS:
        return False, 'Unsupported file type. Allowed: PDF, Word (.doc, .docx), Images (.jpg, .jpeg, .png, .webp).', None, None

    extracted_text = ""

    # Deep signature & integrity validation
    if ext == 'pdf':
        header = file_storage.read(1024)
        file_storage.seek(0)
        if not header.startswith(b'%PDF'):
            return False, 'File content does not match PDF format.', None, None
        try:
            import pypdf
            reader = pypdf.PdfReader(file_storage)
            if len(reader.pages) == 0:
                return False, 'PDF file contains no readable pages.', None, None
            # Safely extract text from first few pages for academic context
            for page in reader.pages[:10]:
                text = page.extract_text()
                if text:
                    extracted_text += text + "\n"
        except Exception:
            return False, 'Invalid or corrupted PDF file.', None, None
        finally:
            file_storage.seek(0)

    elif ext == 'docx':
        header = file_storage.read(4)
        file_storage.seek(0)
        if header != b'PK\x03\x04':
            return False, 'File content does not match DOCX format.', None, None
        try:
            with zipfile.ZipFile(file_storage) as z:
                namelist = z.namelist()
                if '[Content_Types].xml' not in namelist:
                    return False, 'Invalid or corrupted Word document.', None, None
                if 'word/document.xml' in namelist:
                    xml_content = z.read('word/document.xml')
                    tree = ET.fromstring(xml_content)
                    texts = [node.text for node in tree.iter() if node.tag.endswith('}t') and node.text]
                    extracted_text = " ".join(texts)
        except Exception:
            return False, 'Invalid or corrupted Word document.', None, None
        finally:
            file_storage.seek(0)

    elif ext == 'doc':
        header = file_storage.read(8)
        file_storage.seek(0)
        if not (header.startswith(b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1') or header.startswith(b'\xd0\xcf\x11\xe0')):
            return False, 'File content does not match Word (.doc) format.', None, None
        extracted_text = "[Word document attached]"

    elif ext in ('jpg', 'jpeg', 'png', 'webp'):
        header = file_storage.read(32)
        file_storage.seek(0)
        img_type = imghdr.what(None, h=header)
        if ext in ('jpg', 'jpeg'):
            if not header.startswith(b'\xff\xd8\xff') or img_type != 'jpeg':
                return False, 'Invalid or corrupted JPEG image.', None, None
        elif ext == 'png':
            if not header.startswith(b'\x89PNG\r\n\x1a\n') or img_type != 'png':
                return False, 'Invalid or corrupted PNG image.', None, None
        elif ext == 'webp':
            is_webp = (header.startswith(b'RIFF') and len(header) >= 12 and header[8:12] == b'WEBP')
            if not is_webp or img_type != 'webp':
                return False, 'Invalid or corrupted WEBP image.', None, None
        extracted_text = f"[{ext.upper()} image attached]"

    else:
        return False, 'Unsupported file type.', None, None

    # Secure unique storage filename
    unique_name = f"{uuid.uuid4().hex}.{ext}"
    upload_folder = current_app.config.get('UPLOAD_FOLDER', 'uploads')
    save_path = os.path.join(upload_folder, unique_name)

    # Path traversal protection
    upload_folder_abs = os.path.abspath(upload_folder)
    save_path_abs = os.path.abspath(save_path)
    if not save_path_abs.startswith(upload_folder_abs):
        return False, 'Security validation failure.', None, None

    file_storage.save(save_path)
    return True, '', unique_name, extracted_text


@upload_bp.route('/upload', methods=['GET', 'POST'])
def upload_file():
    is_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.is_json

    # Require a logged-in user
    if 'user_id' not in session:
        if is_ajax:
            return jsonify({'error': 'Unauthorized. Please log in.'}), 401
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        if 'file' not in request.files:
            if is_ajax:
                return jsonify({'error': 'No file selected.'}), 400
            flash('No file selected.', 'error')
            return redirect(url_for('upload.upload_file'))

        file = request.files['file']
        valid, msg, unique_name, extracted_text = _validate_and_save_file(file)
        if not valid:
            if is_ajax:
                return jsonify({'error': msg}), 400
            flash(msg, 'error')
            return redirect(url_for('upload.upload_file'))

        # Construct prompt for AI workflow
        user_prompt = request.form.get('prompt', '').strip()
        safe_name = secure_filename(file.filename) or unique_name

        if extracted_text and len(extracted_text.strip()) > 0:
            truncated = extracted_text.strip()[:6000]
            if len(extracted_text.strip()) > 6000:
                truncated += "\n[... Document content truncated for length ...]"

            if user_prompt:
                ai_prompt = f"📎 [Uploaded Document: {safe_name}]\n\n--- Document Content ---\n{truncated}\n\n--- Student Question/Task ---\n{user_prompt}"
            else:
                ai_prompt = f"📎 [Uploaded Document: {safe_name}]\n\n--- Document Content ---\n{truncated}\n\nPlease analyze this document and summarize the key MCA topics and concepts it covers."
        else:
            if user_prompt:
                ai_prompt = f"📎 [Uploaded File: {safe_name}]\n\n{user_prompt}"
            else:
                ai_prompt = f"📎 [Uploaded File: {safe_name}]\n\nPlease review and explain the academic concepts related to this attached MCA study material."

        if is_ajax:
            return jsonify({
                'status': 'success',
                'filename': safe_name,
                'ai_prompt': ai_prompt
            })

        flash('File uploaded successfully.', 'success')
        return redirect(url_for('upload.upload_file'))

    # GET – render upload page
    return render_template('upload.html')

@upload_bp.app_errorhandler(413)
def handle_large_file(e):
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        request.is_json or
        request.path == '/chat' or
        request.path.startswith('/api/')
    )
    if is_ajax:
        return jsonify({'error': 'File size must not exceed 10 MB.'}), 413
    flash('File size must not exceed 10 MB.', 'error')
    return redirect(url_for('upload.upload_file'))
