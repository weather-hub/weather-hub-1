from flask_wtf import FlaskForm
from wtforms import FieldList, FormField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import DataRequired, Optional

from app.modules.dataset.models import PublicationType


class AuthorForm(FlaskForm):
    name = StringField("Name", validators=[DataRequired()])
    affiliation = StringField("Affiliation")
    orcid = StringField("ORCID")
    gnd = StringField("GND")

    class Meta:
        csrf = False  # disable CSRF because is subform

    def get_author(self):
        return {
            "name": self.name.data,
            "affiliation": self.affiliation.data,
            "orcid": self.orcid.data,
        }


class FeatureModelForm(FlaskForm):
    filename = StringField("Filename", validators=[DataRequired()])
    title = StringField("Title", validators=[Optional()])
    desc = TextAreaField("Description", validators=[Optional()])
    publication_type = SelectField(
        "Publication type",
        choices=[("", "-- Select --")] + [(pt.value, pt.name.replace("_", " ").title()) for pt in PublicationType],
        validators=[Optional()],
    )
    tags = StringField("Tags (separated by commas)")
    version = StringField("Version")
    authors = FieldList(FormField(AuthorForm))

    class Meta:
        csrf = False  # disable CSRF because is subform

    def get_authors(self):
        return [author.get_author() for author in self.authors]

    def get_fmmetadata(self):
        publication_type_converted = self.convert_publication_type(self.publication_type.data)
        return {
            "filename": self.filename.data,
            "title": self.title.data or self.filename.data,  # Use filename as default if title is empty
            "description": self.desc.data or "",  # Provide empty string as default
            "publication_type": publication_type_converted,
            "publication_doi": None,
            "tags": self.tags.data,
            "version": self.version.data,
        }

    def convert_publication_type(self, value):
        if not value:  # Handle None or empty string
            return PublicationType.NONE
        for pt in PublicationType:
            if pt.value == value:
                return pt  # Return the enum, not just the .name
        return PublicationType.NONE  # Return the enum, not the string


class DataSetForm(FlaskForm):
    title = StringField("Title", validators=[DataRequired()])
    desc = TextAreaField("Description", validators=[DataRequired()])
    publication_type = SelectField(
        "Publication type",
        choices=[(pt.value, pt.name.replace("_", " ").title()) for pt in PublicationType],
        validators=[DataRequired()],
    )
    tags = StringField("Tags (separated by commas)")
    authors = FieldList(FormField(AuthorForm))
    feature_models = FieldList(FormField(FeatureModelForm), min_entries=1)

    submit = SubmitField("Submit")

    def get_dsmetadata(self):
        publication_type_converted = self.convert_publication_type(self.publication_type.data)

        return {
            "title": self.title.data,
            "description": self.desc.data,
            "publication_type": publication_type_converted,
            "publication_doi": None,
            "dataset_doi": None,
            "tags": self.tags.data,
        }

    def convert_publication_type(self, value):
        if not value:  # Handle None or empty string
            return PublicationType.NONE
        for pt in PublicationType:
            if pt.value == value:
                return pt  # Retornar el enum completo, no solo el .name
        return PublicationType.NONE  # Retornar el enum, no el string

    def get_authors(self):
        return [author.get_author() for author in self.authors]

    def get_feature_models(self):
        return [fm.get_feature_model() for fm in self.feature_models]


class DatasetCommentForm(FlaskForm):
    content = TextAreaField("Comment", validators=[DataRequired()])
    submit = SubmitField("Post Comment")
