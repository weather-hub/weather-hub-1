from datetime import datetime, timezone, timedelta

from core.seeders.BaseSeeder import BaseSeeder
from app.modules.comments.models import Comment
from app.modules.dataset.models import DataSet, DSMetaData
from app.modules.auth.models import User


class CommentsSeeder(BaseSeeder):
	"""Seeder that creates example comments.

	It inserts 5 unapproved comments associated to the dataset titled
	"UVL Models (V1)". The seeder is idempotent in the sense that it will
	first check whether there are already >=5 comments for that dataset and
	will skip insertion if so.
	"""

	priority = 3

	def run(self):
		

		# Buscar el dataset por título en DSMetaData
		dataset = (
			self.db.session.query(DataSet)
			.join(DSMetaData)
			.filter(DSMetaData.title == "UVL Models (V1)")
			.first()
		)

		if not dataset:
			print("[CommentsSeeder] Dataset 'UVL Models (V1)' no encontrado. Saltando seeders de comments.")
			return

		# Comprobar si ya existen suficientes comentarios no aprobados para evitar duplicados
		existing_count = (
			self.db.session.query(Comment).filter(Comment.dataset_id == dataset.id, Comment.approved.is_(False)).count()
		)
		if existing_count >= 5:
			print(f"[CommentsSeeder] Ya existen {existing_count} comentarios no aprobados para dataset id={dataset.id}. No se insertan más.")
			return

		# Obtener hasta 5 usuarios distintos para asignar como autores
		users = self.db.session.query(User).limit(5).all()
		if not users:
			print("[CommentsSeeder] No hay usuarios en la base de datos. Crea usuarios primero.")
			return

		# Si hay menos de 5 usuarios, reutilizarlos en rotación
		comments_to_create = []
		now = datetime.now(timezone.utc)
		sample_texts = [
			"Este dataset es muy útil, gracias por compartirlo.",
			"He encontrado una pequeña discrepancia en la columna 'temp_max'.",
			"¿Alguien sabe qué unidad se usa en la columna 'global_radiation'?",
			"Sería genial tener más ejemplos de uso con este conjunto de datos.",
			"¿Hay planes para añadir más variables meteorológicas?",
		]

		for i in range(5):
			author = users[i % len(users)]
			comment = Comment(
				dataset_id=dataset.id,
				author_id=author.id,
				content=sample_texts[i],
				created_at=(now - timedelta(minutes=5 * i)),
				approved=False,
			)
			comments_to_create.append(comment)

		# Insertar los comentarios
		inserted = self.seed(comments_to_create)

