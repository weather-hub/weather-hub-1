from flask import url_for

from app import db
from app.modules.auth.models import User
from app.modules.auth.services import AuthenticationService
from app.modules.community.models import Community
from app.modules.follow.models import UserAuthorFollow, UserCommunityFollow
from app.modules.follow.services import FollowService


def _login(test_client, email="follower@example.com", password="test1234"):
    """Login helper."""
    return test_client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


# --------------------------TEST--------------------------------------------


def test_follow_unfollow_community_service(test_client):
    app = test_client.application
    follow_service = FollowService()
    auth = AuthenticationService()

    with app.app_context():
        u = auth.create_with_profile(
            name="John",
            surname="Doe",
            email="john_follow_comm@example.com",
            password="pass",
        )
        c = Community(name="Test Community", description="Desc")
        db.session.add(c)
        db.session.commit()

        follow_service.follow_community(u.id, c.id)
        rel = UserCommunityFollow.query.filter_by(user_id=u.id, community_id=c.id).first()
        assert rel is not None

        follow_service.unfollow_community(u.id, c.id)
        rel2 = UserCommunityFollow.query.filter_by(user_id=u.id, community_id=c.id).first()
        assert rel2 is None


def test_follow_unfollow_author_service(test_client):
    app = test_client.application
    follow_service = FollowService()
    auth = AuthenticationService()

    with app.app_context():
        f = auth.create_with_profile(
            name="Ana",
            surname="One",
            email="ana_follow_auth@example.com",
            password="pass",
        )
        a = auth.create_with_profile(
            name="Bob",
            surname="Two",
            email="bob_follow_auth@example.com",
            password="pass",
        )

        follow_service.follow_author(f.id, a.id)
        rel = UserAuthorFollow.query.filter_by(follower_id=f.id, author_id=a.id).first()
        assert rel is not None

        follow_service.unfollow_author(f.id, a.id)
        rel2 = UserAuthorFollow.query.filter_by(follower_id=f.id, author_id=a.id).first()
        assert rel2 is None


def test_get_followed_communities_service(test_client):
    app = test_client.application
    follow_service = FollowService()
    auth = AuthenticationService()

    with app.app_context():
        u = auth.create_with_profile(
            name="Mark",
            surname="One",
            email="mark_followed_comm@example.com",
            password="pass",
        )
        c = Community(name="Community X", description="Desc")
        db.session.add(c)
        db.session.commit()

        follow_service.follow_community(u.id, c.id)

        comms = follow_service.get_followed_communities(u.id)
        ids = [co.id for co in comms]

        assert c.id in ids


def test_get_followed_authors_service(test_client):
    app = test_client.application
    follow_service = FollowService()
    auth = AuthenticationService()

    with app.app_context():
        u = auth.create_with_profile(
            name="Mark2",
            surname="One",
            email="mark_followed_auth@example.com",
            password="pass",
        )
        a = auth.create_with_profile(
            name="Julia",
            surname="Two",
            email="julia_followed_auth@example.com",
            password="pass",
        )

        follow_service.follow_author(u.id, a.id)

        authors = follow_service.get_followed_authors(u.id)
        ids = [au.id for au in authors]

        assert a.id in ids


def test_get_followers_of_author_and_community(test_client):
    app = test_client.application
    follow_service = FollowService()
    auth = AuthenticationService()

    with app.app_context():
        f = auth.create_with_profile(
            name="Follower",
            surname="One",
            email="fol1@example.com",
            password="pass",
        )
        a = auth.create_with_profile(
            name="Author",
            surname="Two",
            email="aut1@example.com",
            password="pass",
        )
        c = Community(name="ComA", description="D")
        db.session.add(c)
        db.session.commit()

        follow_service.follow_author(f.id, a.id)
        follow_service.follow_community(f.id, c.id)

        author_followers = follow_service.get_followers_of_author(a.id)
        community_followers = follow_service.get_followers_of_community(c.id)

        assert len(author_followers) == 1
        assert author_followers[0].id == f.id

        assert len(community_followers) == 1
        assert community_followers[0].id == f.id


def test_notify_dataset_added_to_community_sends_email(test_client, monkeypatch):
    """
    No creamos DataSet real: usamos un objeto dummy con los atributos necesarios.
    """
    app = test_client.application
    follow_service = FollowService()
    sent = {}

    def fake_send_email(subject, recipients, body):
        sent["subject"] = subject
        sent["recipients"] = recipients
        sent["body"] = body

    monkeypatch.setattr("app.modules.follow.services.send_email", fake_send_email)

    with app.app_context():
        author = User(email="author@example.com", password="x")
        follower = User(email="follower@example.com", password="x")
        c = Community(name="CommY", description="Desc")
        db.session.add_all([author, follower, c])
        db.session.commit()

        # follower sigue la comunidad
        follow_service.follow_community(follower.id, c.id)

        # dataset dummy
        class DummyMeta:
            title = "Some Dataset"

        class DummyDataset:
            id = 1
            ds_meta_data = DummyMeta()

        ds = DummyDataset()

        follow_service.notify_dataset_added_to_community(c, ds)

        assert "New dataset in community" in sent["subject"]
        assert follower.email in sent["recipients"]
        assert "Some Dataset" in sent["body"]


def test_notify_dataset_published_sends_email(test_client, monkeypatch):
    """
    Igual que arriba: dataset dummy con user_id.
    """
    app = test_client.application
    follow_service = FollowService()
    sent = {}

    def fake_send_email(subject, recipients, body):
        sent["subject"] = subject
        sent["recipients"] = recipients
        sent["body"] = body

    monkeypatch.setattr("app.modules.follow.services.send_email", fake_send_email)

    with app.app_context():
        author = User(email="author2@example.com", password="x")
        follower = User(email="follower2@example.com", password="x")
        db.session.add_all([author, follower])
        db.session.commit()

        follow_service.follow_author(follower.id, author.id)

        class DummyMeta:
            title = "Author Dataset"

        class DummyDataset:
            id = 2
            ds_meta_data = DummyMeta()
            user_id = author.id

        ds = DummyDataset()

        follow_service.notify_dataset_published(ds)

        assert "New dataset from" in sent["subject"]
        assert follower.email in sent["recipients"]
        assert "Author Dataset" in sent["body"]


def test_follow_unfollow_community_route(test_client):
    app = test_client.application
    auth_service = AuthenticationService()

    with app.app_context():
        user = auth_service.create_with_profile(
            name="User",
            surname="One",
            email="route_comm_user@example.com",
            password="test1234",
        )
        community = Community(name="Community A Route", description="Desc")
        db.session.add(community)
        db.session.commit()

        user_id = user.id
        community_id = community.id

    _login(test_client, "route_comm_user@example.com", "test1234")

    with app.app_context():
        follow_url = url_for("follow.follow_community", community_id=community_id)

    resp = test_client.post(follow_url, follow_redirects=True)
    assert resp.status_code == 200

    with app.app_context():
        assert UserCommunityFollow.query.filter_by(user_id=user_id, community_id=community_id).first() is not None

    with app.app_context():
        unfollow_url = url_for("follow.unfollow_community", community_id=community_id)

    resp2 = test_client.post(unfollow_url, follow_redirects=True)
    assert resp2.status_code == 200

    with app.app_context():
        assert UserCommunityFollow.query.filter_by(user_id=user_id, community_id=community_id).first() is None
