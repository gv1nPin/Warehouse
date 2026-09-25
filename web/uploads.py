"""Файлы документов этапа: сохраняются в media/stage_documents/, в БД пишется только путь."""

import uuid
from pathlib import PurePath

from django.conf import settings
from django.core.files.storage import default_storage

from warehouse.common.dto import NewStageDocument
from warehouse.common.exceptions import ValidationError

UPLOAD_DIR = 'stage_documents'
ALLOWED_EXTENSIONS = {'.pdf', '.jpg', '.jpeg', '.png'}


def save_stage_file(uploaded_file) -> NewStageDocument:
    """Проверяет и сохраняет файл, возвращает его данные для attach_document."""
    if uploaded_file is None:
        raise ValidationError('Выберите файл')

    file_name = PurePath(uploaded_file.name).name
    extension = PurePath(file_name).suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise ValidationError(f'Файл «{file_name}»: можно загрузить только PDF, JPG или PNG')
    if uploaded_file.size > settings.MAX_UPLOAD_SIZE:
        limit_mb = settings.MAX_UPLOAD_SIZE // (1024 * 1024)
        raise ValidationError(f'Файл «{file_name}» больше {limit_mb} МБ')

    storage_path = default_storage.save(f'{UPLOAD_DIR}/{uuid.uuid4().hex}{extension}', uploaded_file)
    return NewStageDocument(
        file_name=file_name,
        storage_path=storage_path,
        content_type=uploaded_file.content_type,
        size_bytes=uploaded_file.size,
    )


def delete_stage_file(storage_path: str) -> None:
    """Удаляет файл документа, если он есть."""
    if storage_path and default_storage.exists(storage_path):
        default_storage.delete(storage_path)


def open_stage_file(storage_path: str):
    """Открывает файл документа на чтение."""
    return default_storage.open(storage_path, 'rb')
