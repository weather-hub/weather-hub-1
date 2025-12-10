import pytest

from app import db
from app.modules.auth.models import User
from app.modules.community.models import ProposalStatus
from app.modules.community.services import MAX_VISUAL_IDENTITY_LENGTH, CommunityService
from app.modules.dataset.models import DataSet, DSMetaData, PublicationType


@pytest.fixture(scope="module")
def test_client(test_client):
    # De auth test
    with test_client.application.app_context():
        pass
    yield test_client


@pytest.fixture
def dataset_factory():
    def _create_dataset(user_id, title="Dataset de Prueba", doi="10.5281/zenodo.12345", tags="tag1,tag2"):
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
        dataset = dataset_factory(user_id=user.id, title="Dataset Publicado")

        service = CommunityService()
        community = service.create_community(name="Comunidad de Dataset")

        proposal = service.propose_dataset(community=community, dataset_id=dataset.id, proposed_by_user_id=user.id)

        assert proposal is not None
        assert proposal.dataset_id == dataset.id
        assert proposal.status == ProposalStatus.PENDING.value


def test_accept_proposal(test_client, dataset_factory):
    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        dataset = dataset_factory(user_id=user.id, title="Dataset Aceptar Propuesta")

        service = CommunityService()
        community = service.create_community(name="Comunidad Aceptar Propuesta")

        proposal = service.propose_dataset(community=community, dataset_id=dataset.id, proposed_by_user_id=user.id)
        service.accept_proposal(proposal)

        assert proposal.status == ProposalStatus.ACCEPTED.value


def test_add_curator(test_client):
    with test_client.application.app_context():
        user = User.query.filter_by(email="test@example.com").first()
        service = CommunityService()
        community = service.create_community(name="Comunidad Test Curador")

        service.add_curator(community, user)

        assert user in community.curators
