from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from warehouse.common.dto import NewStageDocument, StageDocumentDTO
from warehouse.dal.entities import StageDocument
from warehouse.common.mappers import to_stage_document
from .base_repository import BaseRepository


class StageDocumentRepository(BaseRepository[StageDocument]):
    """Документы этапа (StageDocuments): только данные файла, сам файл хранит web-слой."""

    model = StageDocument

    def _select(self):
        return select(StageDocument).options(joinedload(StageDocument.uploader))

    # ---------- Чтение ----------

    def get_by_id(self, document_id: int) -> StageDocumentDTO | None:
        d = self._one(self._select().where(StageDocument.id == document_id))
        return to_stage_document(d) if d else None

    def list_by_stage(self, stage_id: int) -> list[StageDocumentDTO]:
        stmt = self._select().where(StageDocument.stage_id == stage_id).order_by(StageDocument.id)
        return [to_stage_document(d) for d in self._all(stmt)]

    def count_by_stage(self, stage_id: int) -> int:
        stmt = select(func.count()).where(StageDocument.stage_id == stage_id)
        return self.session.scalar(stmt) or 0

    # ---------- Запись ----------

    def add(self, stage_id: int, uploaded_by: int, document: NewStageDocument) -> int:
        entity = StageDocument(
            stage_id=stage_id,
            uploaded_by=uploaded_by,
            file_name=document.file_name,
            storage_path=document.storage_path,
            content_type=document.content_type,
            size_bytes=document.size_bytes,
        )
        return self._add(entity).id

    def delete(self, document_id: int) -> bool:
        return self._delete(document_id)
