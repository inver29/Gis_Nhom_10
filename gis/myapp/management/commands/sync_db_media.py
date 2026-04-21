import mimetypes

from django.core.management.base import BaseCommand

from myapp.models import StoredMediaFile
from myapp.storage import find_legacy_media_path, get_legacy_media_roots, normalize_db_media_name


class Command(BaseCommand):
    help = 'Đồng bộ tất cả file media hiện có từ thư mục media/gis_media vào PostgreSQL.'

    def handle(self, *args, **options):
        imported = 0
        skipped = 0

        for root in get_legacy_media_roots():
            if not root.exists():
                continue

            for file_path in root.rglob('*'):
                if not file_path.is_file():
                    continue

                try:
                    relative_name = file_path.relative_to(root).as_posix()
                    normalized_name = normalize_db_media_name(relative_name)
                except Exception:
                    skipped += 1
                    continue

                if StoredMediaFile.objects.filter(file_name=normalized_name).exists():
                    skipped += 1
                    continue

                file_bytes = file_path.read_bytes()
                StoredMediaFile.objects.create(
                    file_name=normalized_name,
                    content_type=mimetypes.guess_type(normalized_name)[0] or 'application/octet-stream',
                    file_size=len(file_bytes),
                    file_data=file_bytes,
                )
                imported += 1

        self.stdout.write(self.style.SUCCESS(f'Đã nhập {imported} file vào PostgreSQL. Bỏ qua {skipped} file đã tồn tại hoặc không hợp lệ.'))
