from datetime import datetime, timedelta, timezone

from app.modules.comments.models import Comment
from core.seeders.BaseSeeder import BaseSeeder
from app.modules.auth.repositories import UserRepository
from app.modules.dataset.repositories import DataSetRepository



class CommentSeeder(BaseSeeder):
    """
    Seeder para crear comentarios sin aprobar en datasets.
    Crea 5 comentarios sin aprobar en un dataset de user2.
    """

    priority = 20  # Ejecutar después de DatasetSeeder (priority 15)

    def run(self):
        # Verificar que existen usuarios
        
        user_repo = UserRepository()
        dataset_repo = DataSetRepository()

        user1 = user_repo.get_by_email("user1@example.com")
        user2 = user_repo.get_by_email("user2@example.com")

        if not user1 or not user2:
            print("Warning: Users not found. Run AuthSeeder first.")
            return

        # Obtener un dataset de user2
        datasets = dataset_repo.get_by_column("user_id", user2.id)
        if not datasets:
            print("Warning: No dataset found for user2. Run DatasetSeeder first.")
            return

        # Obtener la ÚLTIMA versión del dataset (la más reciente)
        # Ordenar por created_at descendente para obtener la más nueva
        dataset = sorted(datasets, key=lambda d: d.created_at, reverse=True)[0]
        
        print("Seeding unapproved comments...")

        self._create_unapproved_comments(dataset, user1)

        print("Comment seeding completed successfully!")

    def _create_unapproved_comments(self, dataset, comment_author):
        """Crea 5 comentarios sin aprobar en un dataset"""

        comments_data = [
            {
                "content": "This is a great dataset! How can I use it in my research?",
                "days_ago": 7,
            },
            {
                "content": "I found some inconsistencies in the data. Could you check the weather station readings for 2021?",
                "days_ago": 5,
            },
            {
                "content": "Would it be possible to add temperature records from other regions?",
                "days_ago": 3,
            },
            {
                "content": "The metadata documentation is very comprehensive. Thank you for the effort!",
                "days_ago": 2,
            },
            {
                "content": "Are there plans to update this dataset with 2024 data?",
                "days_ago": 1,
            },
        ]

        comments = []
        now = datetime.now(timezone.utc)

        for comment_data in comments_data:
            created_at = now - timedelta(days=comment_data["days_ago"])
            comment = Comment(
                dataset_id=dataset.id,
                author_id=comment_author.id,
                content=comment_data["content"],
                created_at=created_at,
                approved=False,  # No aprobados
            )
            comments.append(comment)

        self.seed(comments)
        print(f"  ✓ Created {len(comments)} unapproved comments for dataset '{dataset.name()}'")
