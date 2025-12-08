from core.seeders.BaseSeeder import BaseSeeder


class DataSetSeeder(BaseSeeder):
    priority = 2  # Lower priority

    def run(self):
        # Los datasets deben crearse manualmente por los usuarios
        # No se crean datasets automáticamente en el seeder
        print("DataSetSeeder: Skipped - datasets should be created manually by users")
