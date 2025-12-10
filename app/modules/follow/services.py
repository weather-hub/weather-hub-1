from flask import url_for

from app import db
from app.modules.auth.models import User
from app.modules.community.models import Community
from app.modules.dataset.models import DataSet
from app.modules.follow.models import UserAuthorFollow, UserCommunityFollow
from app.modules.notifications.service import send_email
from app.modules.profile.models import UserProfile


class FollowService:
    # ---------- COMMUNITIES ----------

    def follow_community(self, user_id: int, community_id: int) -> UserCommunityFollow | None:
        """Empieza a seguir una comunidad. Si ya la sigue, no duplica."""
        existing = UserCommunityFollow.query.filter_by(
            user_id=user_id,
            community_id=community_id,
        ).first()
        if existing:
            return existing

        follow = UserCommunityFollow(user_id=user_id, community_id=community_id)
        db.session.add(follow)
        db.session.commit()
        return follow

    def unfollow_community(self, user_id: int, community_id: int) -> bool:
        """Deja de seguir una comunidad."""
        row = UserCommunityFollow.query.filter_by(
            user_id=user_id,
            community_id=community_id,
        ).first()
        if not row:
            return False

        db.session.delete(row)
        db.session.commit()
        return True

    def get_followed_communities(self, user_id: int):
        communities = (
            Community.query.join(UserCommunityFollow, UserCommunityFollow.community_id == Community.id)
            .filter(UserCommunityFollow.user_id == user_id)
            .all()
        )

        self._attach_dataset_info_to_communities(communities)
        return communities

    def search(self, term: str, current_user_id: int):
        search_communities = Community.query.filter(Community.name.ilike(f"%{term}%")).all()

        self._attach_dataset_info_to_communities(search_communities)

        search_users = (
            User.query.join(UserProfile)
            .filter(
                User.id != current_user_id,
                db.or_(
                    User.email.ilike(f"%{term}%"),
                    UserProfile.name.ilike(f"%{term}%"),
                    UserProfile.surname.ilike(f"%{term}%"),
                ),
            )
            .all()
        )

        return search_communities, search_users

    # ---------- AUTHORS (USERS) ----------

    def follow_author(self, follower_id: int, author_id: int) -> UserAuthorFollow | None:
        """Empieza a seguir a un autor (otro usuario)."""

        if follower_id == author_id:
            return None

        existing = UserAuthorFollow.query.filter_by(
            follower_id=follower_id,
            author_id=author_id,
        ).first()
        if existing:
            return existing

        follow = UserAuthorFollow(follower_id=follower_id, author_id=author_id)
        db.session.add(follow)
        db.session.commit()
        return follow

    def unfollow_author(self, follower_id: int, author_id: int) -> bool:
        """Deja de seguir a un autor."""
        row = UserAuthorFollow.query.filter_by(
            follower_id=follower_id,
            author_id=author_id,
        ).first()
        if not row:
            return False

        db.session.delete(row)
        db.session.commit()
        return True

    def get_followed_authors(self, user_id: int) -> list[User]:
        """Devuelve los autores (usuarios) que el usuario sigue."""
        rows = UserAuthorFollow.query.filter_by(follower_id=user_id).all()
        ids = [r.author_id for r in rows]
        if not ids:
            return []
        return User.query.filter(User.id.in_(ids)).all()

    # ---------- NOTIFICATIONS ----------

    def get_followers_of_author(self, author_id: int) -> list[User]:
        """
        Devuelve los usuarios que siguen a un autor concreto.
        """
        return (
            User.query.join(UserAuthorFollow, UserAuthorFollow.follower_id == User.id)
            .filter(UserAuthorFollow.author_id == author_id)
            .all()
        )

    def get_followers_of_community(self, community_id: int) -> list[User]:
        """
        Devuelve los usuarios que siguen una comunidad concreta.
        """
        return (
            User.query.join(UserCommunityFollow, UserCommunityFollow.user_id == User.id)
            .filter(UserCommunityFollow.community_id == community_id)
            .all()
        )

    def notify_dataset_added_to_community(self, community, dataset):
        """
        Llamar cuando un dataset se acepta en una comunidad.
        Envía email a los usuarios que siguen esa comunidad.
        """
        if community is None or dataset is None:
            return

        followers = self.get_followers_of_community(community.id)
        recipients = {u.email for u in followers if u.email}

        if not recipients:
            return

        title = getattr(dataset.ds_meta_data, "title", f"Dataset #{dataset.id}")

        subject = f"New dataset in community '{community.name}'"

        body_lines = [
            f"A new dataset has been added to a community you follow: {community.name}",
            "",
            f"Title: {title}",
            f"ID: {dataset.id}",
        ]

        body = "\n".join(body_lines)

        send_email(subject, list(recipients), body)

    def notify_dataset_published(self, dataset):
        """
        Llamar cuando un autor publica un nuevo dataset.
        Envía email a los usuarios que siguen a ese autor.
        """
        if dataset is None:
            return

        author = User.query.get(dataset.user_id)
        author_name = "an author"
        if author and getattr(author, "profile", None):
            author_name = f"{author.profile.name} {author.profile.surname}"
        elif author and author.email:
            author_name = author.email

        followers = self.get_followers_of_author(dataset.user_id)
        recipients = {u.email for u in followers if u.email}

        if not recipients:
            return

        title = getattr(dataset.ds_meta_data, "title", f"Dataset #{dataset.id}")

        subject = f"New dataset from {author_name}"

        body_lines = [
            "A new dataset has been published by an author you follow.",
            "",
            f"Author: {author_name}",
            f"Title: {title}",
            f"ID: {dataset.id}",
        ]

        body = "\n".join(body_lines)

        send_email(subject, list(recipients), body)

    # ---------- HELPERS ----------

    def _attach_dataset_info_to_communities(self, communities):
        """
        Rellena dinámicamente proposal.dataset_title y proposal.dataset_url
        para que el HTML de Following pueda mostrar título y enlace correcto.
        NO toca modelos, solo añade atributos en runtime.
        """

        proposal_list = []
        dataset_ids = set()

        for c in communities:
            for p in c.proposals:
                proposal_list.append(p)
                dataset_ids.add(p.dataset_id)

        if not dataset_ids:
            return

        datasets = DataSet.query.filter(DataSet.id.in_(dataset_ids)).all()
        datasets_by_id = {d.id: d for d in datasets}

        for p in proposal_list:
            ds = datasets_by_id.get(p.dataset_id)

            if not ds:
                p.dataset_title = f"Dataset #{p.dataset_id}"
                p.dataset_url = "#"
                continue

            title = None
            if ds.ds_meta_data is not None and ds.ds_meta_data.title:
                title = ds.ds_meta_data.title

            p.dataset_title = title or f"Dataset #{ds.id}"

            doi_url = ds.get_uvlhub_doi()
            if doi_url:
                p.dataset_url = doi_url
            else:
                try:
                    p.dataset_url = url_for("dataset.view", dataset_id=ds.id)
                except Exception:
                    p.dataset_url = f"/dataset/{ds.id}"
