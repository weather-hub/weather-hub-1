from app import db
from app.modules.comments.models import Comment


class CommentService:
    def create_comment(self, dataset_id, author_id, content):
        comment = Comment(
            dataset_id=dataset_id,
            author_id=author_id,
            content=content,
        )
        db.session.add(comment)
        db.session.commit()
        return comment

    def approve_comment(self, comment_id):
        comment = Comment.query.get(comment_id)
        if comment:
            comment.approved = True
            db.session.commit()
        return comment

    def get_comments_for_dataset(self, dataset_id, approved_only=True):
        query = Comment.query.filter_by(dataset_id=dataset_id)
        if approved_only:
            query = query.filter_by(approved=True)

        query = query.order_by(Comment.created_at.desc())
        return query.all()
