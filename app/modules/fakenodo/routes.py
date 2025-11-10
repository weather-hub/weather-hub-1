from flask import jsonify, request, session

from app.modules.fakenodo import fakenodo_bp

# Minimal in-memory store
_store = {}
_next_id = 1


def _get_next_id():
    global _next_id
    nid = _next_id
    _next_id += 1
    return nid


def _generate_doi(deposition_id: int, version: int = 1) -> str:
    return f"10.5072/fakenodo.{deposition_id}.v{version}"


@fakenodo_bp.route("/deposit/depositions", methods=["POST"])
def create_deposition():
    data = request.get_json() or {}
    metadata = data.get("metadata", {})
    dep_id = _get_next_id()
    dep = {
        "id": dep_id,
        "metadata": metadata,
        "files": [],
        "published": False,
        "versions": [],
    }
    _store[dep_id] = dep
    # Return conceptrecid so the client (dataset flow) proceeds
    return jsonify({"id": dep_id, "conceptrecid": dep_id, "metadata": metadata}), 201


@fakenodo_bp.route("/deposit/depositions/<int:deposition_id>/files", methods=["POST"])
def upload_file(deposition_id):
    dep = _store.get(deposition_id)
    if not dep:
        return jsonify({"message": "Deposition not found"}), 404
    uploaded = []
    for key, f in request.files.items():
        filename = f.filename
        content = f.read()
        filesize = len(content)
        dep["files"].append({"filename": filename, "filesize": filesize})
        uploaded.append({"filename": filename, "filesize": filesize})
    return jsonify({"files": uploaded}), 201


@fakenodo_bp.route("/deposit/depositions/<int:deposition_id>/actions/publish", methods=["POST"])
def publish(deposition_id):
    dep = _store.get(deposition_id)
    if not dep:
        return jsonify({"message": "Deposition not found"}), 404
    version = len(dep["versions"]) + 1
    doi = _generate_doi(deposition_id, version)
    snapshot = {"version": version, "doi": doi, "metadata": dict(dep["metadata"]), "files": list(dep["files"])}
    dep["versions"].append(snapshot)
    dep["published"] = True
    return jsonify({"id": deposition_id, "doi": doi}), 202


@fakenodo_bp.route("/deposit/depositions/<int:deposition_id>", methods=["GET"])
def get_deposition(deposition_id):
    dep = _store.get(deposition_id)
    if not dep:
        return jsonify({"message": "Deposition not found"}), 404
    result = dict(dep)
    if dep.get("versions"):
        result["doi"] = dep["versions"][-1]["doi"]
    return jsonify(result), 200


@fakenodo_bp.route("/repository/select", methods=["POST"])
def set_repository():
    """Set which repository backend to use for the current session.

    Body: {"service": "zenodo" | "fakenodo"}
    """
    data = request.get_json() or {}
    service = data.get("service")
    if service not in ("zenodo", "fakenodo"):
        return jsonify({"message": "Invalid service"}), 400
    session["repository_service"] = service
    return jsonify({"service": service}), 200


@fakenodo_bp.route("/repository/current", methods=["GET"])
def get_repository():
    return jsonify({"service": session.get("repository_service", "zenodo")}), 200
