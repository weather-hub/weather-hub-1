from flask_wtf import FlaskForm
from wtforms import SubmitField, TextAreaField
from wtforms.validators import DataRequired, Length


class CommentForm(FlaskForm):

    content = TextAreaField(
        "Comment",
        validators=[
            DataRequired(),
            Length(
                max=50,
                message=(
                    "If you want to leave a comment, please write less than 50 " "characters. Otherwise, use feedbacks."
                ),
            ),
        ],
    )
    submit = SubmitField("Submit")
