from datetime import datetime, timezone

from app import db


class UserCommunityFollow(db.Model):
    __tablename__ = "user_community_follow"

    id = db.Column(db.Integer, primary_key=True)

    # Usuario que sigue
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Comunidad seguida
    community_id = db.Column(db.Integer, db.ForeignKey("community.id"), nullable=False)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    # Relaciones cómodas
    user = db.relationship(
        "User",
        backref=db.backref("followed_communities", lazy="dynamic"),
    )
    community = db.relationship(
        "Community",
        backref=db.backref("followers", lazy="dynamic"),
    )

    __table_args__ = (db.UniqueConstraint("user_id", "community_id", name="uq_user_community_follow"),)

    def __repr__(self):
        return f"<UserCommunityFollow user={self.user_id} community={self.community_id}>"


class UserAuthorFollow(db.Model):
    __tablename__ = "user_author_follow"

    id = db.Column(db.Integer, primary_key=True)

    # Usuario que sigue
    follower_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    # Usuario seguido (autor)
    author_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    follower = db.relationship(
        "User",
        foreign_keys=[follower_id],
        backref=db.backref("authors_followed", lazy="dynamic"),
    )
    author = db.relationship(
        "User",
        foreign_keys=[author_id],
        backref=db.backref("followers_as_author", lazy="dynamic"),
    )

    __table_args__ = (db.UniqueConstraint("follower_id", "author_id", name="uq_user_author_follow"),)

    def __repr__(self):
        return f"<UserAuthorFollow follower={self.follower_id} author={self.author_id}>"
