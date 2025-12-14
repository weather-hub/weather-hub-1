from unittest.mock import MagicMock, Mock

import pytest

from app.modules.dataset.services import DataSetService


class TestDataSetServiceVersioning:
    """
    Tests for versioning-related static methods in DataSetService.
    """

    # Tests for infer_is_major_from_form
    def test_infer_is_major_from_form_with_feature_models(self):
        """
        Test infer_is_major_from_form returns True when form has feature_models.
        """
        mock_form = Mock()
        mock_form.feature_models = ["some_model"]
        assert DataSetService.infer_is_major_from_form(mock_form) is True

    def test_infer_is_major_from_form_with_empty_feature_models(self):
        """
        Test infer_is_major_from_form returns False when form has an empty feature_models list.
        """
        mock_form = Mock()
        mock_form.feature_models = []
        assert DataSetService.infer_is_major_from_form(mock_form) is False

    def test_infer_is_major_from_form_without_feature_models_attribute(self):
        """
        Test infer_is_major_from_form returns False when form lacks the feature_models attribute.
        """
        mock_form = Mock()
        del mock_form.feature_models
        assert DataSetService.infer_is_major_from_form(mock_form) is False

    def test_infer_is_major_from_form_handles_exception(self):
        """
        Test infer_is_major_from_form returns False when an exception occurs.
        """
        mock_form = MagicMock()
        mock_form.feature_models.__len__.side_effect = Exception("Test Exception")
        assert DataSetService.infer_is_major_from_form(mock_form) is False

    # Tests for check_upload_version
    @pytest.mark.parametrize(
        "version, expected_result, expected_message",
        [
            ("1.0.0", True, ""),
            ("v2.3.4", True, ""),
            ("10.20.30", True, ""),
            ("1.2", False, "Version format must be X.Y.Z where X, Y, and Z are integers."),
            ("1.2.3.4", False, "Version format must be X.Y.Z where X, Y, and Z are integers."),
            ("a.b.c", False, "Version components must be integers."),
            ("1.a.3", False, "Version components must be integers."),
            ("1.01.0", False, "Version components must not contain leading zeros.(Ej: 01)"),
            ("v01.0.0", False, "Version components must not contain leading zeros.(Ej: 01)"),
        ],
    )
    def test_check_upload_version(self, version, expected_result, expected_message):
        """
        Test check_upload_version with various valid and invalid version strings.
        """
        is_valid, message = DataSetService.check_upload_version(version)
        assert is_valid == expected_result
        assert message == expected_message

    # Tests for check_introduced_version
    # Tests for check_introduced_version
    @pytest.mark.parametrize(
        "current_version, is_major, form_version, expected_valid, expected_msg",
        [
            # --- CASOS DE FORMATO (Retornan inmediatamente) ---
            # Formato inválido (falta un número)
            ("1.0.0", True, "2.0", False, "Version format must be X.Y.Z where X, Y, and Z are integers."),
            # Formato inválido (letras o estructura mal)
            ("1.0", True, "2.0.0", False, "Version format must be X.Y.Z where X, Y, and Z are integers."),
            # Ceros a la izquierda (Ej: 01)
            ("1.0.0", True, "v2.01.0", False, "Version components must not contain leading zeros.(Ej: 01)"),
            # --- CASOS DE VERSIÓN MAYOR (is_major=True) ---
            # Caso Válido: Sube 1 la mayor, el resto a 0
            ("1.2.3", True, "2.0.0", True, ""),
            # Caso Válido: Con 'v'
            ("v1.2.3", True, "v2.0.0", True, ""),
            # Inválido: La versión mayor no subió (se quedó igual o bajó)
            (
                "1.2.3",
                True,
                "1.0.0",
                False,
                "For a major version, the major version must be increased.(Ej: 1.0.0 to 2.0.0)",
            ),
            # Inválido: Subió la mayor, pero minor/patch no son cero
            # NOTA: Aunque cumple "major increased", falla en la siguiente validación del código.
            (
                "1.2.3",
                True,
                "2.0.1",
                False,
                "For a major version, minor and patch versions must be zero.(Ej: 1.0.0 to 2.0.0)",
            ),
            (
                "1.2.3",
                True,
                "2.1.0",
                False,
                "For a major version, minor and patch versions must be zero.(Ej: 1.0.0 to 2.0.0)",
            ),
            # Inválido: Salto de versión mayor > 1 (Ej: de 1 a 3)
            ("1.2.3", True, "3.0.0", False, "Major version can only be increased by one at a time."),
            # --- CASOS DE VERSIÓN MENOR/PATCH (is_major=False) ---
            # Caso Válido: Sube minor
            ("1.2.3", False, "1.3.0", True, ""),
            # Caso Válido: Sube patch
            ("1.2.3", False, "1.2.4", True, ""),
            # Caso Válido: Con 'v'
            ("v1.2.3", False, "v1.3.4", True, ""),
            ("1.2.3", False, "2.0.0", False, "For a non-major version, minor or patch version must be increased."),
            # Inválido: La versión es idéntica
            ("1.2.3", False, "1.2.3", False, "For a non-major version, minor or patch version must be increased."),
            # Inválido: Downgrade (bajar versión)
            ("1.2.3", False, "1.1.3", False, "For a non-major version, minor or patch version must be increased."),
            ("1.2.3", False, "1.2.2", False, "For a non-major version, minor or patch version must be increased."),
            # Inválido: Salto de versión minor/patch > 1
            ("1.2.3", False, "1.4.0", False, "Minor or patch version can only be increased by one at a time."),
            ("1.2.3", False, "1.2.5", False, "Minor or patch version can only be increased by one at a time."),
            # Inválido: Salto grande en ambos
            ("1.2.3", False, "1.4.5", False, "Minor or patch version can only be increased by one at a time."),
        ],
    )
    def test_check_introduced_version(self, current_version, is_major, form_version, expected_valid, expected_msg):
        """
        Test check_introduced_version with various scenarios for major and minor updates.
        """
        is_valid, message = DataSetService.check_introduced_version(current_version, is_major, form_version)
        assert is_valid == expected_valid
        assert message == expected_msg
