from flask import current_app
from flask_mail import Mail, Message

from app.modules.auth.models import User
from app.modules.dataset.models import DataSet

mail = Mail()


def init_mail(app):
    """Inicializa Flask-Mail con la app principal."""
    mail.init_app(app)


def send_email(subject, recipients, body):
    print(f"send_email called with subject: {subject}, recipients: {recipients}")
    """Envía un correo utilizando Flask-Mail."""
    msg = Message(subject, recipients=recipients, body=body)
    with current_app.app_context():
        mail.send(msg)


def send_dataset_accepted_email(proposal):
    """
    Envía un correo cuando un dataset es aceptado en una comunidad.
    """
    dataset = DataSet.query.get(proposal.dataset_id)
    if not dataset:
        return

    owner = User.query.get(dataset.user_id)
    proposer = User.query.get(proposal.proposed_by)

    recipients = set()

    if owner and owner.email:
        recipients.add(owner.email)

    if proposer and proposer.email:
        recipients.add(proposer.email)

    if not recipients:
        return

    community = proposal.community
    community_name = community.name
    dataset_title = dataset.ds_meta_data.title

    subject = f"Dataset aceptado en {community_name}"

    body = (
        f"Hola,\n\n"
        f'Tu dataset con ID {dataset.id} y título "{dataset_title}" '
        f'ha sido aceptado en la comunidad "{community_name}".\n\n'
        f"¡Enhorabuena!\n\n"
        f"— WeatherHub Team"
    )

    send_email(subject, list(recipients), body)
