from flask_wtf import FlaskForm
from wtforms import BooleanField, FieldList, FormField, SelectField, StringField, SubmitField, TextAreaField
from wtforms.validators import URL, DataRequired, Optional, Regexp

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
    version = StringField(
        "Version",
        validators=[
            DataRequired(),
            Regexp(r"^v\d+\.\d+\.\d+$", message="El formato debe ser vX.Y.Z (ejemplo: v1.0.0)"),
        ],
        render_kw={"placeholder": "v1.0.0"},
        default="v1.0.0",
    )
    authors = FieldList(FormField(AuthorForm))

    class Meta:
        csrf = False  # disable CSRF because is subform

    def get_authors(self):
        return [author.get_author() for author in self.authors]

    def get_fmmetadata(self):
        publication_type_converted = self.convert_publication_type(self.publication_type.data)
        return {
            "filename": self.filename.data,
            # Use filename as default if title is empty
            "title": self.title.data or self.filename.data,
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
    publication_doi = StringField("Publication DOI", validators=[Optional(), URL()])
    version_number = StringField(
        "Version Number",
        validators=[
            DataRequired(),
            Regexp(r"^v\d+\.\d+\.\d+$", message="El formato debe ser vX.Y.Z (ejemplo: v1.0.0)"),
        ],
        render_kw={"placeholder": "v1.0.0"},
        default="v1.0.0",
    )
    tags = StringField("Tags (separated by commas)")
    authors = FieldList(FormField(AuthorForm))
    feature_models = FieldList(FormField(FeatureModelForm), min_entries=1)
    submit = SubmitField("Submit")

    def get_version_number(self):
        return self.version_number.data

    def get_dsmetadata(self):
        publication_type_converted = self.convert_publication_type(self.publication_type.data)

        return {
            "title": self.title.data,
            "description": self.desc.data,
            "publication_type": publication_type_converted,
            "publication_doi": self.publication_doi.data,
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


class DataSetVersionForm(DataSetForm):
    """
    Un formulario para crear una *nueva versión* de un dataset existente.
    Hereda todo de DataSetForm y solo añade el checkbox de "major version".
    """

    feature_models = FieldList(FormField(FeatureModelForm), validators=[Optional()], min_entries=0)

    is_major_version = BooleanField(
        "This is a Major Version (e.g., file changes, new experiments)",
        render_kw={"disabled": True},
        default=False,
        description="Check this if you have changed data files. This will"
        + " generate a new, citable DOI for this version.",
    )

    submit = SubmitField("Publish New Version")
