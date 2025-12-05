from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.auth.models import User
from app.modules.community.models import Community
from app.modules.dataset.models import DataSet
from app.modules.follow.services import FollowService
from app.modules.profile.models import UserProfile

from . import follow_bp

follow_service = FollowService()


def _attach_dataset_info_to_communities(communities):
    for c in communities:
        for p in getattr(c, "proposals", []):
            try:
                ds = DataSet.query.get(p.dataset_id)
                if ds:
                    try:
                        p.dataset_title = ds.ds_meta_data.title
                    except Exception:
                        p.dataset_title = f"Dataset #{p.dataset_id}"

                    try:
                        doi = getattr(ds.ds_meta_data, "dataset_doi", None)
                        if doi:
                            # solo hay link si hay DOI
                            p.dataset_url = url_for("dataset.subdomain_index", doi=doi)
                        else:
                            # sin DOI → sin link
                            p.dataset_url = None
                    except Exception:
                        p.dataset_url = None
                else:
                    p.dataset_title = f"Dataset #{p.dataset_id}"
                    p.dataset_url = None
            except Exception:
                p.dataset_title = f"Dataset #{p.dataset_id}"
                p.dataset_url = None


def _attach_dataset_info(communities):
    """
    Para cada comunidad, rellena p.dataset_title y p.dataset_url
    en sus proposals usando el DataSet real.
    No toca nada de community, solo complementa los objetos.
    """
    for c in communities:
        proposals = getattr(c, "proposals", [])
        for p in proposals:
            # Si ya vienen rellenos de otro sitio, no los pisamos
            if getattr(p, "dataset_title", None) and getattr(p, "dataset_url", None):
                continue

            ds = DataSet.query.get(p.dataset_id)
            if not ds:
                p.dataset_title = f"Dataset #{p.dataset_id}"
                p.dataset_url = "#"
                continue

            p.dataset_title = ds.ds_meta_data.title
            # Usamos el DOI de uvlhub si existe; si no, un fallback neutro
            p.dataset_url = ds.get_uvlhub_doi() or "#"


def _attach_user_datasets(users):
    """
    Para cada usuario, cuelga una lista de datasets en u.following_datasets.
    No toca el modelo User.
    """
    for u in users:
        # Si ya lo hemos calculado antes, no repetir la query
        if hasattr(u, "following_datasets"):
            continue

        u.following_datasets = DataSet.query.filter_by(user_id=u.id).all()


@follow_bp.route("/following", methods=["GET"])
@login_required
def following_index():
    q = request.args.get("q", "").strip()

    # Lo que ya sigues
    followed_communities = follow_service.get_followed_communities(current_user.id)
    followed_authors = follow_service.get_followed_authors(current_user.id)

    # IDs para excluir en búsqueda
    followed_community_ids = [c.id for c in followed_communities]
    followed_author_ids = [u.id for u in followed_authors]

    search_communities = []
    search_users = []

    if q:
        # --------- Comunidades ----------
        communities_query = Community.query.filter(Community.name.ilike(f"%{q}%"))
        # Excluir las que ya sigues
        if followed_community_ids:
            communities_query = communities_query.filter(~Community.id.in_(followed_community_ids))
        search_communities = communities_query.all()

        # --------- Usuarios ----------
        users_query = User.query.join(UserProfile).filter(
            (UserProfile.name.ilike(f"%{q}%")) | (UserProfile.surname.ilike(f"%{q}%")) | (User.email.ilike(f"%{q}%"))
        )

        # Excluirte a ti mismo
        users_query = users_query.filter(User.id != current_user.id)

        # Excluir autores que ya sigues
        if followed_author_ids:
            users_query = users_query.filter(~User.id.in_(followed_author_ids))

        search_users = users_query.all()

    # Si sigues usando los helpers locales, déjalos:
    _attach_dataset_info_to_communities(followed_communities)
    _attach_dataset_info_to_communities(search_communities)
    _attach_user_datasets(followed_authors)
    _attach_user_datasets(search_users)

    return render_template(
        "follow/index.html",
        q=q,
        followed_communities=followed_communities,
        followed_authors=followed_authors,
        search_communities=search_communities,
        search_users=search_users,
    )


# ---------- FOLLOW / UNFOLLOW COMMUNITIES ----------


@follow_bp.route("/follow/community/<int:community_id>", methods=["POST"])
@login_required
def follow_community(community_id):
    follow_service.follow_community(current_user.id, community_id)
    flash("Now you follow this community", "success")
    return redirect(request.referrer or url_for("follow.following_index"))


@follow_bp.route("/unfollow/community/<int:community_id>", methods=["POST"])
@login_required
def unfollow_community(community_id):
    follow_service.unfollow_community(current_user.id, community_id)
    flash("You stopped following this community", "success")
    return redirect(request.referrer or url_for("follow.following_index"))


# ---------- FOLLOW / UNFOLLOW AUTHORS ----------


@follow_bp.route("/follow/author/<int:author_id>", methods=["POST"])
@login_required
def follow_author(author_id):
    follow_service.follow_author(current_user.id, author_id)
    flash("Now you follow this author", "success")
    return redirect(request.referrer or url_for("follow.following_index"))


@follow_bp.route("/unfollow/author/<int:author_id>", methods=["POST"])
@login_required
def unfollow_author(author_id):
    follow_service.unfollow_author(current_user.id, author_id)
    flash("You stopped following this author", "success")
    return redirect(request.referrer or url_for("follow.following_index"))
