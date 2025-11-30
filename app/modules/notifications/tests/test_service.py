import pytest

from app.modules.notifications.service import send_email


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
