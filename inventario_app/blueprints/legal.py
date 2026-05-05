from flask import Blueprint, render_template


bp = Blueprint("legal", __name__)


@bp.route("/privacy-policy", endpoint="privacy_policy")
def privacy_policy():
    return render_template("privacy_policy.html")


@bp.route("/terms", endpoint="terms")
def terms():
    return render_template("terms.html")
