from core.managers.config_manager import ConfigManager
from flask import Flask
from flask_mail import Mail, Message

# Crear app y cargar configuración
app = Flask(__name__)
ConfigManager(app).load_config("production")  # o "development" según entorno

mail = Mail(app)

# Lista del equipo
team = ["miguelmirceballos@gmail.com"]

with app.app_context():
    msg = Message(
        subject="Resumen Diario del Repositorio",
        recipients=team,
        body="Este es el resumen diario de la actividad del repositorio.",
    )
    mail.send(msg)
    print("Correo diario enviado al equipo")
