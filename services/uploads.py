from pathlib import Path
from uuid import uuid4

from flask import current_app, request
from werkzeug.datastructures import FileStorage
from werkzeug.utils import secure_filename


MAX_IMAGE_SIZE = 5 * 1024 * 1024
IMAGE_SIGNATURES = {
    ".jpg": lambda content: content.startswith(b"\xff\xd8\xff"),
    ".jpeg": lambda content: content.startswith(b"\xff\xd8\xff"),
    ".png": lambda content: content.startswith(b"\x89PNG\r\n\x1a\n"),
    ".webp": lambda content: (
        content.startswith(b"RIFF") and content[8:12] == b"WEBP"
    ),
}


def save_uploaded_image(field_name, folder, current_path=None):
    upload: FileStorage | None = request.files.get(field_name)
    if upload is None or not upload.filename:
        return current_path

    extension = Path(secure_filename(upload.filename)).suffix.lower()
    if extension not in IMAGE_SIGNATURES:
        raise ValueError("Choose a JPG, PNG, or WebP image.")

    content = upload.stream.read(MAX_IMAGE_SIZE + 1)
    if len(content) > MAX_IMAGE_SIZE:
        raise ValueError("Images must be 5 MB or smaller.")
    if not IMAGE_SIGNATURES[extension](content):
        raise ValueError("The uploaded file does not match its image type.")

    filename = f"{uuid4().hex}{extension}"
    destination = Path(current_app.static_folder) / "uploads" / folder / filename
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(content)
    return f"uploads/{folder}/{filename}"
