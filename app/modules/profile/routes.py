from flask import redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.modules.auth.services import AuthenticationService
from app.modules.dataset.models import DataSet
from app.modules.profile import profile_bp
from app.modules.profile.forms import UserProfileForm
from app.modules.profile.services import UserProfileService


@profile_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    auth_service = AuthenticationService()
    profile = auth_service.get_authenticated_user_profile
    if not profile:
        return redirect(url_for("public.index"))

    form = UserProfileForm()
    if request.method == "POST":
        service = UserProfileService()
        result, errors = service.update_profile(profile.id, form)
        return service.handle_service_response(
            result, errors, "profile.edit_profile", "Profile updated successfully", "profile/edit.html", form
        )

    return render_template("profile/edit.html", form=form)


@profile_bp.route("/profile/summary")
@login_required
def my_profile():
    page = request.args.get("page", 1, type=int)
    per_page = 5

    user_datasets_pagination = (
        db.session.query(DataSet)
        .filter(DataSet.user_id == current_user.id)
        .order_by(DataSet.created_at.desc())
        .paginate(page=page, per_page=per_page, error_out=False)
    )

    total_datasets_count = db.session.query(DataSet).filter(DataSet.user_id == current_user.id).count()

    print(user_datasets_pagination.items)

    return render_template(
        "profile/summary.html",
        user_profile=current_user.profile,
        user=current_user,
        datasets=user_datasets_pagination.items,
        pagination=user_datasets_pagination,
        total_datasets=total_datasets_count,
    )


@profile_bp.route("/profile/enable-2fa")
@login_required
def enable_2fa():
    import pyotp
    import qrcode
    import io
    import base64
    from flask import session

    secret = pyotp.random_base32()
    current_user.otp_secret = secret
    current_user.twofa_enabled = True
    db.session.commit()

    user_name = current_user.profile.name
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_name, issuer_name="WEATHERHUB")

    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    session['qr_b64'] = qr_b64

    # Pasamos el QR al template del perfil
    return redirect(url_for("profile.edit_profile"))


@profile_bp.route("/profile/disable-2fa")
@login_required
def disable_2fa():
    current_user.otp_secret = None
    current_user.twofa_enabled = False
    db.session.commit()
    return redirect(url_for("profile.edit_profile"))