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


@profile_bp.route("/profile/setup-2fa")
@login_required
def setup_2fa():
    """Genera el QR y el secret temporal, pero NO habilita el 2FA aún"""
    import base64
    import io

    import pyotp
    import qrcode
    from flask import session

    # Generar secret temporal
    secret = pyotp.random_base32()
    session["temp_otp_secret"] = secret  # Guardamos temporalmente en sesión

    # Generar URI para el QR
    user_name = current_user.profile.name
    uri = pyotp.totp.TOTP(secret).provisioning_uri(name=user_name, issuer_name="WEATHERHUB")

    # Generar QR code
    qr = qrcode.make(uri)
    buf = io.BytesIO()
    qr.save(buf, format="PNG")
    qr_b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    session["qr_b64"] = qr_b64

    # Redirigir al perfil (el modal se mostrará automáticamente)
    return redirect(url_for("profile.edit_profile"))


@profile_bp.route("/profile/verify-2fa", methods=["POST"])
@login_required
def verify_2fa():
    """Verifica el código OTP y habilita el 2FA si es correcto"""
    import pyotp
    from flask import flash, request, session

    verification_code = request.form.get("verification_code")
    temp_secret = session.get("temp_otp_secret")

    if not temp_secret:
        flash("Session expired. Please try again.", "error")
        return redirect(url_for("profile.edit_profile"))

    # Verificar el código
    totp = pyotp.TOTP(temp_secret)
    if totp.verify(verification_code, valid_window=1):
        # Código correcto: guardar el secret en el usuario
        current_user.otp_secret = temp_secret
        current_user.twofa_enabled = True
        db.session.commit()

        # Limpiar la sesión
        session.pop("temp_otp_secret", None)
        session.pop("qr_b64", None)

        flash("Two-factor authentication has been enabled successfully!", "success")
    else:
        # Código incorrecto: guardar error en sesión para mostrarlo en el modal, y no con flash en la pagina base
        session["2fa_error"] = "Invalid verification code. Please try again."

    return redirect(url_for("profile.edit_profile"))


@profile_bp.route("/profile/cancel-2fa")
@login_required
def cancel_2fa():
    """Cancela el proceso de configuración de 2FA"""
    from flask import session

    # Limpiar la sesión
    session.pop("temp_otp_secret", None)
    session.pop("qr_b64", None)

    return redirect(url_for("profile.edit_profile"))


@profile_bp.route("/profile/disable-2fa")
@login_required
def disable_2fa():
    from flask import flash

    """Deshabilita el 2FA del usuario"""
    current_user.otp_secret = None
    current_user.twofa_enabled = False
    db.session.commit()

    flash("Two-factor authentication has been disabled.", "success")
    return redirect(url_for("profile.edit_profile"))
