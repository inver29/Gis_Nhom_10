import mimetypes
from io import BytesIO
from pathlib import Path, PurePosixPath
from uuid import uuid4

from django.apps import apps
from django.conf import settings
from django.core.files.base import File
from django.core.files.storage import Storage
from django.urls import reverse
from django.utils.deconstruct import deconstructible


def normalize_db_media_name(name):
    raw_name = str(name or '').strip().replace('\\', '/')
    if not raw_name:
        raise ValueError('Tên file không hợp lệ.')

    media_prefixes = []
    media_url = str(getattr(settings, 'MEDIA_URL', '/media/') or '/media/')
    if media_url:
        media_prefixes.append(media_url.rstrip('/'))
    media_prefixes.append('/db-media')

    for prefix in media_prefixes:
        if raw_name.startswith(prefix + '/'):
            raw_name = raw_name[len(prefix) + 1:]
            break

    cleaned = PurePosixPath('/' + raw_name.lstrip('/')).as_posix().lstrip('/')
    parts = [part for part in cleaned.split('/') if part and part != '.']
    if not parts or any(part == '..' for part in parts):
        raise ValueError('Tên file không hợp lệ.')
    return '/'.join(parts)


def build_db_media_url(name):
    cleaned = normalize_db_media_name(name)
    return reverse('db_media_file', kwargs={'file_name': cleaned})


def get_legacy_media_roots():
    roots = []
    configured_root = getattr(settings, 'MEDIA_ROOT', None)
    if configured_root:
        roots.append(Path(configured_root))

    roots.extend([
        Path(settings.BASE_DIR) / 'media',
        Path(settings.BASE_DIR).parent / 'media',
        Path(settings.BASE_DIR).parent / 'gis_media',
    ])

    unique_roots = []
    seen = set()
    for root in roots:
        resolved = str(Path(root))
        if resolved not in seen:
            seen.add(resolved)
            unique_roots.append(Path(root))
    return unique_roots


def find_legacy_media_path(name):
    cleaned = normalize_db_media_name(name)
    for root in get_legacy_media_roots():
        candidate = (root / cleaned).resolve()
        try:
            candidate.relative_to(root.resolve())
        except Exception:
            continue
        if candidate.is_file():
            return candidate
    return None


@deconstructible
class DatabaseMediaStorage(Storage):
    def _model(self):
        return apps.get_model('myapp', 'StoredMediaFile')

    def _normalize_name(self, name):
        return normalize_db_media_name(name)

    def _open(self, name, mode='rb'):
        normalized = self._normalize_name(name)
        media_obj = self._model().objects.only('file_data').get(file_name=normalized)
        return File(BytesIO(bytes(media_obj.file_data)), name=normalized)

    def _save(self, name, content):
        normalized = self.get_available_name(self._normalize_name(name))

        if hasattr(content, 'seek'):
            try:
                content.seek(0)
            except Exception:
                pass

        file_bytes = content.read()
        if isinstance(file_bytes, memoryview):
            file_bytes = file_bytes.tobytes()
        if not isinstance(file_bytes, (bytes, bytearray)):
            file_bytes = bytes(file_bytes)

        content_type = getattr(content, 'content_type', '') or mimetypes.guess_type(normalized)[0] or 'application/octet-stream'
        self._model().objects.update_or_create(
            file_name=normalized,
            defaults={
                'content_type': content_type,
                'file_size': len(file_bytes),
                'file_data': bytes(file_bytes),
            },
        )
        return normalized

    def delete(self, name):
        normalized = self._normalize_name(name)
        self._model().objects.filter(file_name=normalized).delete()

    def exists(self, name):
        normalized = self._normalize_name(name)
        return self._model().objects.filter(file_name=normalized).exists()

    def size(self, name):
        normalized = self._normalize_name(name)
        return self._model().objects.only('file_size').get(file_name=normalized).file_size

    def url(self, name):
        return build_db_media_url(name)

    def get_available_name(self, name, max_length=None):
        normalized = self._normalize_name(name)
        if not self.exists(normalized):
            return normalized

        candidate_path = PurePosixPath(normalized)
        stem = candidate_path.stem
        suffix = candidate_path.suffix
        parent = '' if str(candidate_path.parent) == '.' else str(candidate_path.parent)

        while True:
            candidate = f"{stem}_{uuid4().hex[:7]}{suffix}"
            if parent:
                candidate = f"{parent}/{candidate}"
            if not self.exists(candidate):
                if max_length and len(candidate) > max_length:
                    overflow = len(candidate) - max_length
                    stem = stem[:-overflow] if overflow < len(stem) else uuid4().hex[:8]
                    continue
                return candidate

    def path(self, name):
        raise NotImplementedError('Database storage does not expose filesystem paths.')
