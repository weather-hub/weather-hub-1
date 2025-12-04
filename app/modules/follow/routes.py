from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.auth.models import User
from app.modules.community.models import Community
from app.modules.dataset.models import DataSet
from app.modules.follow.services import FollowService
from app.modules.profile.models import UserProfile

from . import follow_bp

follow_service = FollowService()


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
    """
    Pantalla principal de 'Following':
    - buscador de usuarios y comunidades
    - listas de comunidades seguidas y autores seguidos
    """
    q = request.args.get("q", "").strip()

    # Lo que ya sigues
    followed_communities = follow_service.get_followed_communities(current_user.id)
    followed_authors = follow_service.get_followed_authors(current_user.id)

    # Sets de ids para filtrar búsquedas
    followed_community_ids = {c.id for c in followed_communities}
    followed_author_ids = {u.id for u in followed_authors}

    search_communities = []
    search_users = []

    if q:
        # Comunidades por nombre
        raw_search_communities = Community.query.filter(Community.name.ilike(f"%{q}%")).all()

        # Usuarios por nombre, apellido o email (ya excluimos al propio user)
        raw_search_users = (
            User.query.join(UserProfile)
            .filter(
                (UserProfile.name.ilike(f"%{q}%"))
                | (UserProfile.surname.ilike(f"%{q}%"))
                | (User.email.ilike(f"%{q}%"))
            )
            .filter(User.id != current_user.id)
            .all()
        )

        # ⬇️ FILTRO: quitar los que ya sigo
        search_communities = [c for c in raw_search_communities if c.id not in followed_community_ids]

        search_users = [u for u in raw_search_users if u.id not in followed_author_ids]
        # ⬆️ FILTRO

    # Completar info de comunidades (dataset_title/dataset_url)
    _attach_dataset_info(followed_communities)
    _attach_dataset_info(search_communities)

    # Completar datasets de usuarios
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
