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

    def get_comments_for_dataset(self, dataset, user):
    
        if user and user.id == dataset.user_id:
            return Comment.query \
                .filter_by(dataset_id=dataset.id) \
                .order_by(Comment.created_at.desc()) \
                .all()

        return Comment.query.filter(
            Comment.dataset_id == dataset.id,
            db.or_(Comment.approved == True, Comment.author_id == user.id)
        ).order_by(Comment.created_at.desc()).all()

    def get_comments_for_dataset(self, dataset, user=None):
            
            if user and user.is_authenticated and user.id == dataset.user_id:
                comments = Comment.query.filter_by(dataset_id=dataset.id).order_by(Comment.created_at.desc()).all()
            elif user and user.is_authenticated:
                comments = Comment.query.filter(Comment.dataset_id == dataset.id,db.or_(Comment.approved == True, Comment.author_id == user.id)).order_by(Comment.created_at.desc()).all()
            else:
                comments = Comment.query.filter_by(dataset_id=dataset.id, approved=True).order_by(Comment.created_at.desc()).all()

            return comments