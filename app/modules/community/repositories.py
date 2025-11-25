from typing import List, Optional

from app.modules.community.models import Community, CommunityDatasetProposal
from core.repositories.BaseRepository import BaseRepository


class CommunityRepository(BaseRepository):
    def __init__(self):
        super().__init__(Community)

    def get_by_name(self, name: str) -> Optional[Community]:
        return self.session.query(Community).filter(Community.name == name).first()


class CommunityDatasetProposalRepository(BaseRepository):
    def __init__(self):
        super().__init__(CommunityDatasetProposal)

    def get_pending_by_community(self, community_id: int) -> List[CommunityDatasetProposal]:
        return (
            self.session.query(CommunityDatasetProposal)
            .filter(CommunityDatasetProposal.community_id == community_id, CommunityDatasetProposal.status == "pending")
            .all()
        )

    def get_by_dataset_and_community(self, dataset_id: int, community_id: int) -> Optional[CommunityDatasetProposal]:
        return (
            self.session.query(CommunityDatasetProposal)
            .filter(
                CommunityDatasetProposal.dataset_id == dataset_id, CommunityDatasetProposal.community_id == community_id
            )
            .first()
        )
