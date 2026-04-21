from urllib.parse import quote
import re
import unicodedata

from django.conf import settings
from django.core.files.storage import default_storage

from .storage import build_db_media_url, normalize_db_media_name


def encode_public_url(raw_url):
    clean_url = (raw_url or "").strip()
    if not clean_url:
        return ""
    return quote(clean_url, safe='/:?=&%')


def resolve_media_url(image_field):
    if not image_field:
        return ""

    raw_name = ""
    try:
        raw_name = (image_field.name or "").strip()
    except Exception:
        raw_name = str(image_field).strip()

    if raw_name.startswith(("http://", "https://")):
        return encode_public_url(raw_name)

    if raw_name.startswith("/"):
        return normalize_gallery_url(raw_name)

    try:
        return encode_public_url(image_field.url)
    except Exception:
        return normalize_gallery_url(raw_name)


def normalize_gallery_url(raw_url):
    clean_url = (raw_url or "").strip()
    if not clean_url:
        return ""

    if clean_url.startswith(("http://", "https://")):
        return encode_public_url(clean_url)

    if clean_url.startswith("/"):
        media_prefix = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").rstrip("/")
        if clean_url.startswith(f"{media_prefix}/") or clean_url.startswith("/db-media/"):
            try:
                return encode_public_url(build_db_media_url(clean_url))
            except Exception:
                return encode_public_url(clean_url)
        return encode_public_url(clean_url)

    try:
        return encode_public_url(default_storage.url(normalize_db_media_name(clean_url)))
    except Exception:
        media_url = (getattr(settings, "MEDIA_URL", "/media/") or "/media/").rstrip("/")
        return encode_public_url(f"{media_url}/{clean_url.lstrip('/')}")


def fold_text_for_match(value):
    raw_value = str(value or "").replace("\u0110", "D").replace("\u0111", "d").replace("\u00c4\x90", "D").replace("\u00c4\u2018", "d")
    normalized = unicodedata.normalize("NFKD", raw_value).encode("ascii", "ignore").decode("ascii")
    normalized = re.sub(r"[^a-zA-Z0-9]+", " ", normalized).strip().casefold()
    return re.sub(r"\s+", " ", normalized)


def build_medicine_catalog_key(name, unit, manufacturer=""):
    return (
        fold_text_for_match(name),
        fold_text_for_match(unit),
        fold_text_for_match(manufacturer),
    )


MEDICINE_SHARED_SYNC_FIELDS = (
    "name",
    "product_type",
    "category",
    "unit",
    "short_description",
    "manufacturer",
    "origin",
    "price",
    "image",
    "gallery_urls",
    "description",
    "usage",
    "ingredients",
    "dosage",
    "prescription_required",
)


def get_medicine_catalog_key_for_instance(medicine):
    return build_medicine_catalog_key(
        getattr(medicine, "name", ""),
        getattr(medicine, "unit", ""),
        getattr(medicine, "manufacturer", ""),
    )


def get_medicine_image_name(medicine):
    image_field = getattr(medicine, "image", None)
    if not image_field:
        return ""
    try:
        return (image_field.name or "").strip()
    except Exception:
        return str(image_field or "").strip()


def sync_medicine_catalog_metadata(source_medicine, *, previous_catalog_key=None, field_names=None, queryset=None):
    if source_medicine is None or not getattr(source_medicine, "pk", None):
        return []

    selected_fields = [
        field_name
        for field_name in MEDICINE_SHARED_SYNC_FIELDS
        if field_names is None or field_name in set(field_names)
    ]
    if not selected_fields:
        return []

    target_keys = {
        get_medicine_catalog_key_for_instance(source_medicine),
    }
    if previous_catalog_key:
        target_keys.add(previous_catalog_key)
    target_keys = {key for key in target_keys if any(key)}
    if not target_keys:
        return []

    model_class = source_medicine.__class__
    queryset = queryset if queryset is not None else model_class.objects.all()
    related_medicines = [
        candidate
        for candidate in queryset.exclude(pk=source_medicine.pk).order_by("id")
        if get_medicine_catalog_key_for_instance(candidate) in target_keys
    ]
    if not related_medicines:
        return []

    source_image_name = get_medicine_image_name(source_medicine)
    updated_ids = []

    for candidate in related_medicines:
        update_fields = []
        for field_name in selected_fields:
            if field_name == "image":
                if get_medicine_image_name(candidate) != source_image_name:
                    candidate.image = source_image_name
                    update_fields.append("image")
                continue

            source_value = getattr(source_medicine, field_name)
            if getattr(candidate, field_name) != source_value:
                setattr(candidate, field_name, source_value)
                update_fields.append(field_name)

        if update_fields:
            candidate.save(update_fields=update_fields)
            updated_ids.append(candidate.pk)

    return updated_ids


def build_gallery_urls_from_text(raw_text):
    urls = []
    for raw_url in (raw_text or "").splitlines():
        clean_url = normalize_gallery_url(raw_url)
        if clean_url and clean_url not in urls:
            urls.append(clean_url)
    return urls


def build_gallery_urls(instance):
    urls = []

    primary_url = resolve_media_url(getattr(instance, "image", None))
    if primary_url:
        urls.append(primary_url)

    for clean_url in build_gallery_urls_from_text(getattr(instance, "gallery_urls", "") or ""):
        if clean_url not in urls:
            urls.append(clean_url)

    return urls
