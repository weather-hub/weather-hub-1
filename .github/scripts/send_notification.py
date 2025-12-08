import os
import smtplib
import ssl
from email.message import EmailMessage


def send_email():
    # 1. Obtener variables de entorno (Configuradas en el YAML)
    sender_email = os.environ.get("MAIL_USERNAME")
    password = os.environ.get("MAIL_PASSWORD")
    smtp_server = os.environ.get("MAIL_SERVER", "smtp.gmail.com")  # Ejemplo por defecto
    smtp_port = int(os.environ.get("MAIL_PORT", 465))

    # Lista de destinatarios (puede ser una variable de entorno también)
    team = ["miguelmirceballos@gmail.com"]

    msg = EmailMessage()
    msg["Subject"] = "🚀 Notificación de Push: Rama Trunk Actualizada"
    msg["From"] = sender_email
    msg["To"] = ", ".join(team)
    msg.set_content(
        "Se ha realizado un merge/push exitoso a la rama trunk.\n\n"
        "Por favor, haced 'git pull' para actualizar vuestros entornos locales."
    )

    # 2. Enviar el correo usando contexto seguro SSL
    context = ssl.create_default_context()

    try:
        with smtplib.SMTP_SSL(smtp_server, smtp_port, context=context) as server:
            server.login(sender_email, password)
            server.send_message(msg)
            print(f"✅ Correo enviado exitosamente a: {team}")
    except Exception as e:
        print(f"❌ Error al enviar el correo: {e}")
        exit(1)  # Forzar fallo en el Action si el correo no sale


if __name__ == "__main__":
    send_email()
