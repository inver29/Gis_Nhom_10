from pathlib import Path
import mimetypes

from django.conf import settings
from django.db import migrations, models


def normalize_name(raw_name):
    value = str(raw_name or '').strip().replace('\\', '/')
    if not value:
        return ''

    prefixes = []
    media_url = str(getattr(settings, 'MEDIA_URL', '/media/') or '/media/').rstrip('/')
    if media_url:
        prefixes.append(media_url)
    prefixes.append('/db-media')

    for prefix in prefixes:
        if value.startswith(prefix + '/'):
            value = value[len(prefix) + 1:]
            break

    parts = [part for part in value.lstrip('/').split('/') if part and part not in {'.', '..'}]
    return '/'.join(parts)


def candidate_roots():
    roots = [
        Path(getattr(settings, 'MEDIA_ROOT', settings.BASE_DIR.parent / 'gis_media')),
        Path(settings.BASE_DIR) / 'media',
        Path(settings.BASE_DIR).parent / 'media',
        Path(settings.BASE_DIR).parent / 'gis_media',
    ]
    unique = []
    seen = set()
    for root in roots:
        marker = str(root)
        if marker not in seen:
            seen.add(marker)
            unique.append(root)
    return unique


def import_media_from_roots(apps, schema_editor):
    StoredMediaFile = apps.get_model('myapp', 'StoredMediaFile')

    for root in candidate_roots():
        if not root.exists():
            continue

        for file_path in root.rglob('*'):
            if not file_path.is_file():
                continue

            try:
                relative_name = file_path.relative_to(root).as_posix()
            except Exception:
                continue

            normalized_name = normalize_name(relative_name)
            if not normalized_name:
                continue

            if StoredMediaFile.objects.filter(file_name=normalized_name).exists():
                continue

            file_bytes = file_path.read_bytes()
            StoredMediaFile.objects.create(
                file_name=normalized_name,
                content_type=mimetypes.guess_type(normalized_name)[0] or 'application/octet-stream',
                file_size=len(file_bytes),
                file_data=file_bytes,
            )


def noop_reverse(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('myapp', '0001_initial'),
    ]

    operations = [
        migrations.CreateModel(
            name='StoredMediaFile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('file_name', models.CharField(db_index=True, max_length=500, unique=True)),
                ('content_type', models.CharField(blank=True, max_length=255)),
                ('file_size', models.PositiveIntegerField(default=0)),
                ('file_data', models.BinaryField()),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
            ],
            options={
                'verbose_name': 'Tệp media trong PostgreSQL',
                'verbose_name_plural': 'Tệp media trong PostgreSQL',
                'ordering': ['file_name'],
            },
        ),
        migrations.RunPython(import_media_from_roots, noop_reverse),
    ]
