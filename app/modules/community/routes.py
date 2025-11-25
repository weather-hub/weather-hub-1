from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.modules.community.repositories import CommunityRepository
from app.modules.community.services import CommunityService
from app.modules.dataset.models import DataSet

from . import community_bp


@community_bp.route("/community/", methods=["GET"])
def index():
    repo = CommunityRepository()
    communities = repo.session.query(repo.model).all()

    for c in communities:
        for p in getattr(c, "proposals", []):
            try:
                ds = DataSet.query.get(p.dataset_id)
                if ds:
                    try:
                        p.dataset_title = ds.ds_meta_data.title
                    except Exception:
                        p.dataset_title = f"Dataset #{p.dataset_id}"
                    # COger el enlace par poder redirigir directamente
                    try:
                        if hasattr(ds.ds_meta_data, "dataset_doi") and ds.ds_meta_data.dataset_doi:
                            p.dataset_url = url_for("dataset.subdomain_index", doi=ds.ds_meta_data.dataset_doi)
                        else:
                            p.dataset_url = url_for("dataset.get_unsynchronized_dataset", dataset_id=ds.id)
                    except Exception:
                        p.dataset_url = "#"
                else:
                    p.dataset_title = f"Dataset #{p.dataset_id}"
                    p.dataset_url = "#"
            except Exception:
                p.dataset_title = f"Dataset #{p.dataset_id}"
                p.dataset_url = "#"

    return render_template("community/index.html", communities=communities)


@community_bp.route("/community/create", methods=["POST"])
@login_required
def create():
    name = request.form.get("name")
    description = request.form.get("description")
    visual_identity = request.form.get("visual_identity")

    svc = CommunityService()
    try:
        svc.create_community(name=name, description=description, visual_identity=visual_identity)
        flash("Community created", "success")
    except ValueError as e:
        # Ya existe ese nombre
        flash(str(e), "error")

    return redirect(url_for("community.index"))


def get_or_redirect_community(svc, community_id):
    community = svc.repository.get_by_id(community_id)
    if not community:
        flash("Community not found", "error")
        return redirect(url_for("community.index"))
    return community


def user_is_curator(community, user):
    try:
        return any(u.id == user.id for u in community.curators)
    except Exception:
        return False


def handle_proposal_action(community_id, proposal_id, action):
    svc = CommunityService()
    community = get_or_redirect_community(svc, community_id)
    if not isinstance(community, object) or not getattr(community, "id", None):
        return community

    if not user_is_curator(community, current_user):
        flash("Only curators can manage proposals", "error")
        return redirect(url_for("community.index"))

    proposal = svc.proposal_repository.get_by_id(proposal_id)
    if not proposal or proposal.community_id != community.id:
        flash("Proposal not found", "error")
        return redirect(url_for("community.index"))

    if action == "accept":
        svc.accept_proposal(proposal)
        flash("Proposal accepted", "success")
    elif action == "reject":
        svc.reject_proposal(proposal)
        flash("Proposal rejected", "success")
    elif action == "remove":
        deleted = svc.proposal_repository.delete(proposal_id)
        flash(
            "Dataset removed from community" if deleted else "Failed to remove dataset",
            "success" if deleted else "error",
        )

    return redirect(url_for("community.index"))


@community_bp.route("/community/<int:community_id>/propose", methods=["POST"])
@login_required
def propose_dataset(community_id):
    dataset_id = int(request.form.get("dataset_id"))
    user = current_user
    svc = CommunityService()

    community = get_or_redirect_community(svc, community_id)
    if not isinstance(community, object) or not getattr(community, "id", None):
        return community

    proposal = svc.propose_dataset(community, dataset_id, user.id)
    is_curator = user_is_curator(community, user)

    if proposal and is_curator:
        svc.accept_proposal(proposal)
        flash("Dataset proposed and accepted (you are a curator)", "success")
    else:
        flash("Dataset proposed to community (pending curator approval)", "success")

    return redirect(url_for("community.index"))


@community_bp.route("/community/<int:community_id>/join", methods=["POST"])
@login_required
def join(community_id):
    svc = CommunityService()
    community = get_or_redirect_community(svc, community_id)
    if not isinstance(community, object) or not getattr(community, "id", None):
        return community

    svc.add_curator(community, current_user)
    flash("You are now a curator of the community", "success")
    return redirect(url_for("community.index"))


@community_bp.route("/community/<int:community_id>/leave", methods=["POST"])
@login_required
def leave(community_id):
    svc = CommunityService()
    community = get_or_redirect_community(svc, community_id)
    if not isinstance(community, object) or not getattr(community, "id", None):
        return community

    svc.remove_curator(community, current_user)
    flash("You left the community", "success")
    return redirect(url_for("community.index"))


@community_bp.route("/community/<int:community_id>/proposal/<int:proposal_id>/accept", methods=["POST"])
@login_required
def accept_proposal(community_id, proposal_id):
    return handle_proposal_action(community_id, proposal_id, "accept")


@community_bp.route("/community/<int:community_id>/proposal/<int:proposal_id>/reject", methods=["POST"])
@login_required
def reject_proposal(community_id, proposal_id):
    return handle_proposal_action(community_id, proposal_id, "reject")


@community_bp.route("/community/<int:community_id>/proposal/<int:proposal_id>/remove", methods=["POST"])
@login_required
def remove_proposal(community_id, proposal_id):
    return handle_proposal_action(community_id, proposal_id, "remove")
