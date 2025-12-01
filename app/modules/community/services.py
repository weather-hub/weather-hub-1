from app import db
from app.modules.auth.models import User
from app.modules.community.models import Community, CommunityDatasetProposal
from app.modules.community.repositories import CommunityDatasetProposalRepository, CommunityRepository
from core.services.BaseService import BaseService
from app.modules.notifications.service import send_dataset_accepted_email



class CommunityService(BaseService):
    def __init__(self):
        super().__init__(CommunityRepository())
        self.proposal_repository = CommunityDatasetProposalRepository()

    def create_community(self, name: str, description: str = None, visual_identity: str = None) -> Community:
        existing = self.repository.get_by_name(name)
        if existing:
            raise ValueError("Community name already exists")

        return self.repository.create(name=name, description=description, visual_identity=visual_identity)

    def add_curator(self, community: Community, user: User):
        if user not in community.curators:
            community.curators.append(user)
            db.session.commit()
        return community

    def remove_curator(self, community: Community, user: User):
        if user in community.curators:
            community.curators.remove(user)
            db.session.commit()
        return community

    def propose_dataset(
        self, community: Community, dataset_id: int, proposed_by_user_id: int
    ) -> CommunityDatasetProposal:
        existing = self.proposal_repository.get_by_dataset_and_community(dataset_id, community.id)
        if existing:
            return existing
        return self.proposal_repository.create(
            community_id=community.id, dataset_id=dataset_id, proposed_by=proposed_by_user_id
        )

    def accept_proposal(self, proposal):
        proposal.accept()
        db.session.commit()

        try:
            send_dataset_accepted_email(proposal)
        except Exception:
            pass

        return proposal
    def reject_proposal(self, proposal: CommunityDatasetProposal):
        proposal.reject()
        db.session.commit()
        return proposal
