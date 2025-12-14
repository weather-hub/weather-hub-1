import pytest

from app import db
from app.modules.auth.models import User
from app.modules.community.models import Community, CommunityDatasetProposal, ProposalStatus
from app.modules.community.services import MAX_VISUAL_IDENTITY_LENGTH, CommunityService
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType


def _login(test_client, email="test@example.com", password="test1234"):
    """Login helper."""
    return test_client.post(
        "/login",
        data={"email": email, "password": password},
        follow_redirects=True,
    )


def _logout(test_client):
    """Logout helper."""
    return test_client.get("/logout", follow_redirects=True)


@pytest.fixture(scope="module")
def test_client(test_client):
    # De auth test
    with test_client.application.app_context():
        pass
    yield test_client


@pytest.fixture
def dataset_factory():
    def _create_dataset(user_id, title="Dataset de Prueba", doi="10.5281/fakenodo.12345", tags="tag1,tag2"):
        meta = DSMetaData(
            title=title,
            description=f"Descripción para {title}",
            publication_type=PublicationType.NONE,
            dataset_doi=doi,
            tags=tags,
        )
        db.session.add(meta)
        db.session.flush()

        dataset = DataSet(user_id=user_id, ds_meta_data_id=meta.id)
        db.session.add(dataset)
        db.session.commit()
        return dataset

    return _create_dataset


def test_create_community_success(test_client):
    with test_client.application.app_context():
        service = CommunityService()
        community = service.create_community(
            name="Comunidad de Prueba",
            description="Una comunidad de prueba",
            visual_identity="https://example.com/imagen.png",
        )

        assert community is not None
        assert community.name == "Comunidad de Prueba"
        assert community.description == "Una comunidad de prueba"


def test_create_community_duplicate_name(test_client):
    with test_client.application.app_context():
        service = CommunityService()
        service.create_community(name="Comunidad Duplicada")

        with pytest.raises(ValueError, match="Community name already exists"):
            service.create_community(name="Comunidad Duplicada")


def test_create_community_visual_identity_too_long(test_client):
    with test_client.application.app_context():
        service = CommunityService()
        long_url = "https://google.com/" + "67" * MAX_VISUAL_IDENTITY_LENGTH

        with pytest.raises(ValueError, match="Visual identity URL is too long"):
            service.create_community(name="Comunidad URL Larga", visual_identity=long_url)


def test_propose_published_dataset(test_client, dataset_factory):
    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = dataset_factory(user_id=user.id, title="Dataset Test 1")

        service = CommunityService()
        community = service.create_community(name="Community Test 1")

        proposal = service.propose_dataset(community=community, dataset_id=dataset.id, proposed_by_user_id=user.id)

        assert proposal is not None
        assert proposal.dataset_id == dataset.id
        assert proposal.status == ProposalStatus.PENDING.value


def test_accept_proposal(test_client, dataset_factory):
    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = dataset_factory(user_id=user.id, title="Dataset Test 2")

        service = CommunityService()
        community = service.create_community(name="Community Test 2")

        proposal = service.propose_dataset(community=community, dataset_id=dataset.id, proposed_by_user_id=user.id)
        service.accept_proposal(proposal)

        assert proposal.status == ProposalStatus.ACCEPTED.value


def test_add_curator(test_client):
    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        service = CommunityService()
        community = service.create_community(name="Community Test 3")

        service.add_curator(community, user)

        assert user in community.curators


def test_index_route(test_client):
    resp = test_client.get("/community/")
    assert resp.status_code == 200


def test_create_community_route_requires_login(test_client):
    _logout(test_client)
    resp = test_client.post("/community/create", data={"name": "Test"}, follow_redirects=True)
    assert b"Login" in resp.data or b"login" in resp.data


def test_create_community_route_success(test_client):
    _logout(test_client)
    _login(test_client)

    resp = test_client.post(
        "/community/create",
        data={
            "name": "Community Test 4",
            "description": "Descripcion de prueba",
            "visual_identity": "https://example.com/img.png",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


def test_propose_dataset_route(test_client, dataset_factory):
    _logout(test_client)
    app = test_client.application

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = dataset_factory(user_id=user.id, title="Dataset Test 5")
        svc = CommunityService()
        community = svc.create_community(name="Community Test 5")
        dataset_id = dataset.id
        community_id = community.id

    _login(test_client)

    resp = test_client.post(
        f"/community/{community_id}/propose",
        data={"dataset_id": dataset_id},
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        proposal = CommunityDatasetProposal.query.filter_by(community_id=community_id, dataset_id=dataset_id).first()
        assert proposal is not None


def test_join_community_route(test_client):
    _logout(test_client)
    app = test_client.application

    with app.app_context():
        community = Community(name="Community Test 6", description="Desc")
        db.session.add(community)
        db.session.commit()
        community_id = community.id

    _login(test_client)

    resp = test_client.post(f"/community/{community_id}/join", follow_redirects=True)
    assert resp.status_code == 200
    assert b"curator" in resp.data.lower()


def test_leave_community_route(test_client):
    _logout(test_client)
    app = test_client.application

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        svc = CommunityService()
        community = svc.create_community(name="Community Test 7")
        svc.add_curator(community, user)
        community_id = community.id

    _login(test_client)

    resp = test_client.post(f"/community/{community_id}/leave", follow_redirects=True)
    assert resp.status_code == 200
    assert b"left" in resp.data.lower()


def test_accept_proposal_route(test_client, dataset_factory):
    _logout(test_client)
    app = test_client.application

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = dataset_factory(user_id=user.id, title="Dataset Test 8")
        svc = CommunityService()
        community = svc.create_community(name="Community Test 8")
        svc.add_curator(community, user)
        proposal = svc.propose_dataset(community, dataset.id, user.id)
        community_id = community.id
        proposal_id = proposal.id

    _login(test_client)

    resp = test_client.post(
        f"/community/{community_id}/proposal/{proposal_id}/accept",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        p = CommunityDatasetProposal.query.get(proposal_id)
        assert p.status == ProposalStatus.ACCEPTED.value


def test_reject_proposal_route(test_client, dataset_factory):
    _logout(test_client)
    app = test_client.application

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = dataset_factory(user_id=user.id, title="Dataset Test 9")
        svc = CommunityService()
        community = svc.create_community(name="Community Test 9")
        svc.add_curator(community, user)
        proposal = svc.propose_dataset(community, dataset.id, user.id)
        proposal.status = ProposalStatus.PENDING.value
        db.session.commit()
        community_id = community.id
        proposal_id = proposal.id

    _login(test_client)

    resp = test_client.post(
        f"/community/{community_id}/proposal/{proposal_id}/reject",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        p = CommunityDatasetProposal.query.get(proposal_id)
        assert p.status == ProposalStatus.REJECTED.value


def test_remove_proposal_route(test_client, dataset_factory):
    _logout(test_client)
    app = test_client.application

    with app.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = dataset_factory(user_id=user.id, title="Dataset Test 10")
        svc = CommunityService()
        community = svc.create_community(name="Community Test 10")
        svc.add_curator(community, user)
        proposal = svc.propose_dataset(community, dataset.id, user.id)
        svc.accept_proposal(proposal)
        community_id = community.id
        proposal_id = proposal.id

    _login(test_client)

    resp = test_client.post(
        f"/community/{community_id}/proposal/{proposal_id}/remove",
        follow_redirects=True,
    )
    assert resp.status_code == 200

    with app.app_context():
        p = CommunityDatasetProposal.query.get(proposal_id)
        assert p is None


def test_join_nonexistent_community_route(test_client):
    _logout(test_client)
    _login(test_client)

    resp = test_client.post("/community/99999/join", follow_redirects=True)
    assert resp.status_code == 200
    assert b"not found" in resp.data.lower()
