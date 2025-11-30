from flask import abort, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.modules.comments import comments_bp
from app.modules.comments.forms import CommentForm
from app.modules.comments.services import CommentService
from app.modules.dataset.models import DataSet

comment_service = CommentService()


@comments_bp.route("/dataset/<int:dataset_id>", methods=["GET", "POST"])
@login_required
def comment_on_dataset(dataset_id):
    dataset = DataSet.query.get_or_404(dataset_id)
    comment_form = CommentForm()

    if comment_form.validate_on_submit():
        comment_service.create_comment(
            dataset_id=dataset.id,
            author_id=current_user.id,
            content=comment_form.content.data,
        )
        doi = dataset.ds_meta_data.dataset_doi
        subdomain_url = url_for("dataset.subdomain_index", doi=doi)
        return redirect(subdomain_url)

    return render_template(
        "comments/coments.html",
        dataset=dataset,
        comment_form=comment_form,
    )


@comments_bp.route("/comments/<int:comment_id>/approve", methods=["POST"])
@login_required
def approve_comment(comment_id):
    comment = comment_service.approve_comment(comment_id)
    if not comment:
        abort(404)
    # Solo el autor del dataset puede aprobar
    if comment.dataset.user_id != current_user.id:
        abort(403)
    doi = comment.dataset.ds_meta_data.dataset_doi
    return redirect(url_for("dataset.subdomain_index", doi=doi))
