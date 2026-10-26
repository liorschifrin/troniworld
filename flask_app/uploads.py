"""Validated image uploads (T05 slice 3).

An upload is accepted only when Pillow can open and verify it as PNG, JPEG,
GIF, or WebP, and it is at most MAX_IMAGE_BYTES. The bytes are written to a
temporary file in the upload folder and renamed into place only after
validation. The image is never re-encoded.
"""
import os
import tempfile
import uuid

from flask import abort, current_app, jsonify, request, send_from_directory
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

MAX_IMAGE_BYTES = 20 * 1024 * 1024
MAX_REQUEST_BYTES = 25 * 1024 * 1024
# Pillow format name -> extensions that format may carry.
IMAGE_FORMATS = {
    'PNG': {'png'},
    'JPEG': {'jpg', 'jpeg'},
    'GIF': {'gif'},
    'WEBP': {'webp'},
}
UPLOAD_URL_PREFIX = '/static/uploads/'
COPY_CHUNK = 1024 * 1024
MAX_STORED_NAME_BYTES = 255  # common filesystem file-name limit


class UploadError(Exception):
    def __init__(self, message, status):
        super().__init__(message)
        self.message = message
        self.status = status


def _image_format(path):
    """Return the Pillow format of the file at path, or None if it is not a valid image."""
    # Image.open + verify() checks structure without decoding; reopen to read the format
    # because verify() leaves the image unusable.
    try:
        with Image.open(path) as probe:
            probe.verify()
        with Image.open(path) as image:
            return image.format
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError, Image.DecompressionBombError):
        return None


def _bounded_name(original, extension, prefix):
    """Shorten original so prefix + name fits MAX_STORED_NAME_BYTES, keeping its extension."""
    budget = MAX_STORED_NAME_BYTES - len(prefix.encode()) - len(extension.encode()) - 1
    stem = original[:-(len(extension) + 1)]
    stem = stem.encode()[:max(budget, 0)].decode(errors='ignore')
    return f'{stem}.{extension}'


def save_image(file_storage, folder):
    """Validate an uploaded image and store it in folder. Return the stored file name."""
    original = secure_filename(file_storage.filename or '')
    extension = original.rsplit('.', 1)[1].lower() if '.' in original else ''
    if extension not in set().union(*IMAGE_FORMATS.values()):
        raise UploadError('Invalid image type', 400)

    handle, temp_path = tempfile.mkstemp(dir=folder, prefix='.upload-', suffix='.tmp')
    try:
        size = 0
        with os.fdopen(handle, 'wb') as out:
            while chunk := file_storage.stream.read(COPY_CHUNK):
                size += len(chunk)
                if size > MAX_IMAGE_BYTES:
                    raise UploadError('Image is larger than the 20 MB limit', 413)
                out.write(chunk)
        image_format = _image_format(temp_path)
        if image_format not in IMAGE_FORMATS or extension not in IMAGE_FORMATS[image_format]:
            raise UploadError('File is not a valid PNG, JPEG, GIF, or WebP image', 400)
        prefix = f'{uuid.uuid4().hex}_'
        name = prefix + _bounded_name(original, extension, prefix)
        os.chmod(temp_path, 0o644)  # mkstemp creates 0600
        os.replace(temp_path, os.path.join(folder, name))
        return name
    finally:
        if os.path.exists(temp_path):
            os.unlink(temp_path)


def init_app(app):
    app.config['MAX_CONTENT_LENGTH'] = MAX_REQUEST_BYTES

    @app.before_request
    def reject_oversized_declared_length():
        # MAX_CONTENT_LENGTH is only enforced when a view reads the body; body-ignoring
        # routes (the static view) would otherwise accept any declared length.
        if (request.content_length or 0) > MAX_REQUEST_BYTES:
            abort(413)

    @app.errorhandler(413)
    def too_large(error):
        from .csrf import FORM_ENDPOINTS
        if request.endpoint in FORM_ENDPOINTS | {'static', None} and request.headers.get('X-Requested-With') != 'XMLHttpRequest':
            return error
        return jsonify(error='Request is larger than the 25 MB limit'), 413

    @app.route(UPLOAD_URL_PREFIX + '<path:filename>')
    def uploaded_file(filename):
        # Serves UPLOAD_FOLDER at the public upload URL, so the folder may live
        # outside flask_app/static (T13). When it is the default folder this is
        # the same file the static view would send.
        return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

    @app.after_request
    def nosniff_uploads(response):
        if request.path.startswith(UPLOAD_URL_PREFIX):
            response.headers['X-Content-Type-Options'] = 'nosniff'
        return response
