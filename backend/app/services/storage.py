import io
import os
import uuid
from flask import current_app, has_app_context
from werkzeug.utils import secure_filename

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_EVIDENCE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp', 'pdf'}

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PRIVATE_UPLOADS_DIR = os.path.join(BACKEND_DIR, 'private_uploads', 'claims')


def _private_uploads_dir():
    if has_app_context() and current_app.config.get('PRIVATE_UPLOAD_DIR'):
        return current_app.config['PRIVATE_UPLOAD_DIR']
    return PRIVATE_UPLOADS_DIR


def _looks_like_image(file_storage):
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if header.startswith(b'\xff\xd8\xff'):
        return True  # JPEG
    if header.startswith(b'\x89PNG\r\n\x1a\n'):
        return True  # PNG
    if header.startswith((b'GIF87a', b'GIF89a')):
        return True  # GIF
    if header[:4] == b'RIFF' and header[8:12] == b'WEBP':
        return True  # WEBP
    return False


def _looks_like_evidence(file_storage):
    header = file_storage.stream.read(16)
    file_storage.stream.seek(0)
    if header.startswith(b'%PDF-'):
        return True
    return _looks_like_image(file_storage)


def _gcs_client():
    try:
        from google.cloud import storage as gcs
        return gcs.Client()
    except Exception:
        return None


def _s3_client():
    bucket = os.environ.get('S3_PUBLIC_BUCKET') or os.environ.get('S3_BUCKET')
    if not bucket:
        return None, None
    try:
        import boto3
        client = boto3.client(
            's3',
            endpoint_url=os.environ.get('S3_ENDPOINT_URL') or None,
            aws_access_key_id=os.environ.get('S3_ACCESS_KEY_ID') or os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('S3_SECRET_ACCESS_KEY') or os.environ.get('AWS_SECRET_ACCESS_KEY'),
            region_name=os.environ.get('S3_REGION') or os.environ.get('AWS_REGION', 'auto'),
        )
        return client, bucket
    except Exception:
        return None, None


def save_public_image(file_storage, subfolder):
    """Guarda imagen pública en Google Cloud Storage (GCS), S3/Cloudflare R2 o en static/images/<subfolder>."""
    if not file_storage or not file_storage.filename:
        return None

    ext = file_storage.filename.rsplit('.', 1)[-1].lower() if '.' in file_storage.filename else ''
    if ext not in ALLOWED_IMAGE_EXTENSIONS or not _looks_like_image(file_storage):
        return None

    filename = f"{uuid.uuid4().hex}_{secure_filename(file_storage.filename)}"
    content_type = file_storage.mimetype or f"image/{ext}"

    # 1. Google Cloud Storage (nativo en Cloud Run mediante ADC)
    gcs_bucket_name = os.environ.get('GCS_PUBLIC_BUCKET')
    if gcs_bucket_name:
        gcs_client = _gcs_client()
        if gcs_client:
            blob_path = f"public/{subfolder}/{filename}"
            blob = gcs_client.bucket(gcs_bucket_name).blob(blob_path)
            blob.upload_from_file(file_storage.stream, content_type=content_type)
            cdn_base = (os.environ.get('PUBLIC_CDN_URL') or '').rstrip('/')
            if cdn_base:
                return f"{cdn_base}/{blob_path}"
            return f"https://storage.googleapis.com/{gcs_bucket_name}/{blob_path}"

    # 2. S3 / Cloudflare R2
    client, bucket = _s3_client()
    if client and bucket:
        key = f"public/{subfolder}/{filename}"
        client.upload_fileobj(
            file_storage.stream,
            bucket,
            key,
            ExtraArgs={'ContentType': content_type},
        )
        cdn_base = (os.environ.get('S3_PUBLIC_BASE_URL') or os.environ.get('PUBLIC_CDN_URL') or '').rstrip('/')
        if cdn_base:
            return f"{cdn_base}/{key}"
        return key

    # 3. Disco local (desarrollo)
    app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    upload_folder = os.path.join(app_dir, 'static', 'images', subfolder)
    os.makedirs(upload_folder, exist_ok=True)
    file_storage.save(os.path.join(upload_folder, filename))
    return filename


def save_private_evidence(file_storage):
    """Guarda documentación sensible de reclamaciones (CIF, facturas, licencias)
    FUERA de /static/, en GCS privado, S3 privado o carpeta privada local."""
    if not file_storage or not file_storage.filename:
        return None

    ext = file_storage.filename.rsplit('.', 1)[-1].lower() if '.' in file_storage.filename else ''
    if ext not in ALLOWED_EVIDENCE_EXTENSIONS or not _looks_like_evidence(file_storage):
        return None

    filename = f"{uuid.uuid4().hex}.{ext}"
    content_type = file_storage.mimetype or 'application/octet-stream'

    # 1. Google Cloud Storage privado (nativo en GCP mediante IAM/ADC)
    gcs_priv = os.environ.get('GCS_PRIVATE_BUCKET')
    if gcs_priv:
        gcs_client = _gcs_client()
        if gcs_client:
            blob_path = f"claims/{filename}"
            blob = gcs_client.bucket(gcs_priv).blob(blob_path)
            blob.upload_from_file(file_storage.stream, content_type=content_type)
            return f"gs://{gcs_priv}/{blob_path}"

    # 2. S3 / R2 privado
    private_bucket = os.environ.get('S3_PRIVATE_BUCKET') or os.environ.get('S3_BUCKET')
    client, _ = _s3_client()
    if client and private_bucket:
        key = f"private/claims/{filename}"
        client.upload_fileobj(
            file_storage.stream,
            private_bucket,
            key,
            ExtraArgs={'ContentType': content_type},
        )
        return f"s3://{private_bucket}/{key}"

    # 3. Directorio privado local fuera de /static/
    target_dir = _private_uploads_dir()
    os.makedirs(target_dir, exist_ok=True)
    dest = os.path.join(target_dir, filename)
    file_storage.save(dest)
    return filename


def download_gcs_private_evidence(gs_uri):
    """Descarga en memoria un documento privado gs://<bucket>/<key> usando ADC de Cloud Run."""
    if not gs_uri or not gs_uri.startswith('gs://'):
        return None, None
    parts = gs_uri[5:].split('/', 1)
    if len(parts) != 2:
        return None, None
    gcs_client = _gcs_client()
    if not gcs_client:
        return None, None
    blob = gcs_client.bucket(parts[0]).blob(parts[1])
    if not blob.exists():
        return None, None
    data = blob.download_as_bytes()
    return io.BytesIO(data), (blob.content_type or 'application/octet-stream')


def get_private_evidence_path(filename):
    """Resuelve de forma segura un fichero de evidencia local impidiendo path traversal."""
    if not filename or filename.startswith(('s3://', 'gs://')):
        return None
    safe_name = os.path.basename(filename)
    if safe_name != filename:
        return None
    full_path = os.path.join(_private_uploads_dir(), safe_name)
    if os.path.isfile(full_path):
        return full_path
    return None
