from datetime import datetime, timezone
from enum import Enum

from app import db

# Many to many de usuarios y comunidades
community_curators = db.Table(
    "community_curators",
    db.Column("community_id", db.Integer, db.ForeignKey("community.id"), primary_key=True),
    db.Column("user_id", db.Integer, db.ForeignKey("user.id"), primary_key=True),
)


class ProposalStatus(Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class Community(db.Model):
    __tablename__ = "community"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(200), unique=True, nullable=False)
    description = db.Column(db.Text)
    visual_identity = db.Column(db.String(1024))
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    curators = db.relationship("User", secondary=community_curators, backref=db.backref("communities", lazy="dynamic"))

    proposals = db.relationship("CommunityDatasetProposal", backref="community", lazy=True, cascade="all, delete")

    def __repr__(self):
        return f"<Community {self.name}>"


class CommunityDatasetProposal(db.Model):
    __tablename__ = "community_dataset_proposal"

    id = db.Column(db.Integer, primary_key=True)
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=False)
    dataset_id = db.Column(db.Integer, db.ForeignKey("data_set.id"), nullable=False)
    proposed_by = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    status = db.Column(db.String(20), nullable=False, default=ProposalStatus.PENDING.value)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))

    def is_pending(self) -> bool:
        return self.status == ProposalStatus.PENDING.value

    def accept(self):
        self.status = ProposalStatus.ACCEPTED.value

    def reject(self):
        self.status = ProposalStatus.REJECTED.value

    def __repr__(self):
        return (
            f"<CommunityDatasetProposal community={self.community_id} dataset={self.dataset_id} status={self.status}>"
        )
