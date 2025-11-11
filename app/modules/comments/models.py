from datetime import datetime

from app import db


class Comment(db.Model):
    id = db.Column(
        db.Integer,
        primary_key=True,
    )

    dataset_id = db.Column(
        db.Integer,
        db.ForeignKey("data_set.id"),
        nullable=False,
    )

    author_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False,
    )

    content = db.Column(db.Text, nullable=False)

    created_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
    )

    # solo dataset author puede aprobar
    approved = db.Column(
        db.Boolean,
        default=False,
    )

    user = db.relationship("User", backref="comment")
    dataset = db.relationship("DataSet", backref="comment")
