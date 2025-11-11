from config import ConfigManager
from flask import Flask
from flask_mail import Mail, Message

# Crear app y cargar configuración
app = Flask(__name__)
ConfigManager(app).load_config("production")  # o "development" según entorno

mail = Mail(app)

# Lista del equipo
team = ["dev1@example.com", "dev2@example.com", "dev3@example.com"]

with app.app_context():
    msg = Message(
        subject="Notificación de Push a la Rama Principal",
        recipients=team,
        body="Se ha hecho un push a la rama main del repositorio. Revisa los cambios recientes.",
    )
    mail.send(msg)
    print("Correo de push enviado al equipo")
