from app.modules.fakenodo.models import FakenodoDeposition, FakenodoFile, FakenodoVersion
from core.repositories.BaseRepository import BaseRepository


class FakenodoDepositionRepository(BaseRepository):
    def __init__(self):
        super().__init__(FakenodoDeposition)


class FakenodoFileRepository(BaseRepository):
    def __init__(self):
        super().__init__(FakenodoFile)


class FakenodoVersionRepository(BaseRepository):
    def __init__(self):
        super().__init__(FakenodoVersion)
