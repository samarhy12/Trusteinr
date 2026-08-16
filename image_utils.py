import os
import uuid

from werkzeug.utils import secure_filename

try:
    from PIL import Image, UnidentifiedImageError
except ImportError:  # pragma: no cover
    Image = None
    UnidentifiedImageError = Exception


def validate_and_save_image(file_storage, prefix, upload_folder, allowed_extensions, max_dimension=1600):
    """
    Validate an uploaded file is actually a real image (not just a file with an
    image-like extension), then re-encode it as a clean JPEG before saving.
    Re-encoding strips EXIF metadata and neutralizes polyglot-file tricks where
    malicious content is smuggled inside what looks like an image.

    Returns the stored filename, "__invalid__" if the file isn't a valid image,
    or None if no file was provided.
    """
    if not file_storage or not file_storage.filename:
        return None

    ext = file_storage.filename.rsplit(".", 1)[-1].lower() if "." in file_storage.filename else ""
    if ext not in allowed_extensions:
        return "__invalid__"

    try:
        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)
        image.verify()  # raises if the file isn't a genuine, uncorrupted image

        file_storage.stream.seek(0)
        image = Image.open(file_storage.stream)  # verify() consumes the image object; reopen to actually use it
        image = image.convert("RGB")
    except (UnidentifiedImageError, OSError, ValueError, AttributeError):
        return "__invalid__"

    if max(image.size) > max_dimension:
        image.thumbnail((max_dimension, max_dimension))

    os.makedirs(upload_folder, exist_ok=True)
    filename = secure_filename(f"{prefix}-{uuid.uuid4().hex[:8]}.jpg")
    image.save(os.path.join(upload_folder, filename), "JPEG", quality=88)
    return filename


def delete_upload(filename, upload_folder):
    if not filename:
        return
    path = os.path.join(upload_folder, filename)
    if os.path.exists(path):
        try:
            os.remove(path)
        except OSError:
            pass
