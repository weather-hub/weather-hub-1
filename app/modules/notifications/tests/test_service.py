from types import SimpleNamespace

import pytest

from app.modules.notifications.service import send_dataset_accepted_email, send_email


def test_send_email(test_app, mocker):
    """Test básico de envío de email."""
    mock_message = mocker.patch("app.modules.notifications.service.Message")
    mock_send = mocker.patch("app.modules.notifications.service.mail.send")

    with test_app.app_context():
        send_email("Test Subject", ["recipient@example.com"], "Test Body")

    mock_message.assert_called_once_with("Test Subject", recipients=["recipient@example.com"], body="Test Body")
    mock_send.assert_called_once()


def test_send_email_multiple_recipients(test_app, mocker):
    """Test de envío a múltiples destinatarios."""
    mock_message = mocker.patch("app.modules.notifications.service.Message")
    mock_send = mocker.patch("app.modules.notifications.service.mail.send")

    recipients = ["user1@example.com", "user2@example.com", "user3@example.com"]

    with test_app.app_context():
        send_email("Announcement", recipients, "Hello everyone!")

    mock_message.assert_called_once_with("Announcement", recipients=recipients, body="Hello everyone!")
    mock_send.assert_called_once()


def test_send_email_failure(test_app, mocker):
    """Test que verifica el comportamiento cuando falla el envío."""
    mocker.patch("app.modules.notifications.service.Message")
    mocker.patch("app.modules.notifications.service.mail.send", side_effect=Exception("SMTP connection failed"))

    with test_app.app_context():
        with pytest.raises(Exception, match="SMTP connection failed"):
            send_email("Subject", ["test@example.com"], "Body")


# Test para las notificaciones de aceptacion de datasets en comunidades


def test_send_dataset_accepted_email_happy_path(test_app, mocker):
    """Cuando el dataset existe y tanto owner como proposer tienen email, se envía correo a ambos."""

    dataset = SimpleNamespace(id=123, user_id=10, ds_meta_data=SimpleNamespace(title="My Dataset"))
    proposal = SimpleNamespace(dataset_id=123, proposed_by=20, community=SimpleNamespace(name="Climate"))

    owner = SimpleNamespace(id=10, email="owner@example.com")
    proposer = SimpleNamespace(id=20, email="proposer@example.com")

    mock_dataset_class = SimpleNamespace(query=SimpleNamespace(get=lambda pk: dataset))
    mocker.patch("app.modules.notifications.service.DataSet", new=mock_dataset_class)

    def user_get_side_effect(user_id):
        if user_id == 10:
            return owner
        if user_id == 20:
            return proposer
        return None

    mock_user_class = SimpleNamespace(query=SimpleNamespace(get=user_get_side_effect))
    mocker.patch("app.modules.notifications.service.User", new=mock_user_class)
    mock_send_email = mocker.patch("app.modules.notifications.service.send_email")

    send_dataset_accepted_email(proposal)

    mock_send_email.assert_called_once()
    called_subject, called_recipients, called_body = mock_send_email.call_args[0]
    assert "Climate" in called_subject
    assert set(called_recipients) == {"owner@example.com", "proposer@example.com"}
    assert "My Dataset" in called_body
    assert "ID 123" in called_body or "123" in called_body


def test_send_dataset_accepted_email_no_recipients(test_app, mocker):
    """Si ni el owner ni el proposer tienen email, no se envía nada."""
    dataset = SimpleNamespace(id=5, user_id=11, ds_meta_data=SimpleNamespace(title="NoEmails"))
    proposal = SimpleNamespace(dataset_id=5, proposed_by=12, community=SimpleNamespace(name="Community"))

    owner = SimpleNamespace(id=11, email=None)
    proposer = SimpleNamespace(id=12, email=None)

    mock_dataset_class = SimpleNamespace(query=SimpleNamespace(get=lambda pk: dataset))
    mocker.patch("app.modules.notifications.service.DataSet", new=mock_dataset_class)
    mock_user_class = SimpleNamespace(query=SimpleNamespace(get=lambda uid: owner if uid == 11 else proposer))
    mocker.patch("app.modules.notifications.service.User", new=mock_user_class)
    mock_send_email = mocker.patch("app.modules.notifications.service.send_email")

    send_dataset_accepted_email(proposal)

    mock_send_email.assert_not_called()


def test_send_dataset_accepted_email_dataset_missing(test_app, mocker):
    """Si el dataset no existe, la función retorna sin intentar enviar correo."""
    proposal = SimpleNamespace(dataset_id=9999, proposed_by=1, community=SimpleNamespace(name="X"))

    mock_dataset_class = SimpleNamespace(query=SimpleNamespace(get=lambda pk: None))
    mocker.patch("app.modules.notifications.service.DataSet", new=mock_dataset_class)
    mock_send_email = mocker.patch("app.modules.notifications.service.send_email")

    send_dataset_accepted_email(proposal)

    mock_send_email.assert_not_called()
