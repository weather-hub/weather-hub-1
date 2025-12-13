"""
Tests for the Explore form.
"""

from app.modules.explore.forms import ExploreForm


def test_explore_form_creation(test_app):
    """
    ExploreForm should be instantiable within an app context.
    """
    with test_app.app_context():
        form = ExploreForm()
        assert form is not None
        assert hasattr(form, "submit")
