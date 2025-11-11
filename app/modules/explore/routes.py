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
    # Normaliza tags en lista
    tags_raw = (request.args.get("tags") or "").strip()
    tags = [t.strip() for t in tags_raw.split(",") if t.strip()]

    filters = dict(
        query=request.args.get("query", "").strip(),
        sorting=request.args.get("sort_by", "newest"),
        publication_type=request.args.get("publication_type", "any"),
        tags=tags,
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
