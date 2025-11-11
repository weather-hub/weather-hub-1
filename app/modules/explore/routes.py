from flask import Blueprint, render_template, request

from .services import ExploreService

explore_bp = Blueprint(
    "explore",
    __name__,
    url_prefix="/explore",
    template_folder="templates",
)


@explore_bp.route("/", methods=["GET"])
def index():

    filters = dict(
        query=request.args.get("query", "").strip(),
        sorting=request.args.get("sort_by", "newest"),
        publication_type=request.args.get("publication_type", "any"),
        tags=request.args.get("tags") or "".strip(),
        start_date=request.args.get("start_date") or None,
        end_date=request.args.get("end_date") or None,
    )

    datasets = ExploreService().filter(**filters)

    return render_template(
        "explore/index.html",
        datasets=datasets,
        query=filters["query"],
        request_args=request.args,
    )


# For dinamic frontend implementation @explore_bp.route("/", methods=["POST"])
