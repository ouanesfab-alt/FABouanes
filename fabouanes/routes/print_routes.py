from __future__ import annotations

from datetime import datetime

from fabouanes.fastapi_compat import flash, g, redirect, render_template, request, send_file, url_for

from fabouanes.core.decorators import login_required
from fabouanes.routes.route_utils import bind_route
from fabouanes.services.print_service import PRINT_LAYOUT, build_print_payload, generate_invoice_pdf


def register_print_routes(app):
    @login_required
    def print_document(doc_type: str, item_id: int):
        payload = build_print_payload(doc_type, item_id)
        if not payload:
            flash("Document introuvable pour impression.", "danger")
            return redirect(url_for("index"))

        printed_at = datetime.now()
        payload = {
            **payload,
            "printed_date": printed_at.strftime("%Y-%m-%d"),
            "printed_time": printed_at.strftime("%H:%M"),
        }

        if request.args.get("format") == "pdf":
            pdf_buffer = generate_invoice_pdf(payload, g.user["username"])
            if pdf_buffer:
                return send_file(
                    pdf_buffer,
                    mimetype="application/pdf",
                    as_attachment=True,
                    download_name=f"{payload['number']}.pdf",
                )
            flash("Generation PDF indisponible. Affichage HTML utilise a la place.", "warning")

        return render_template(
            "print_document.html",
            doc=payload,
            printed_by=g.user["username"],
            print_layout=PRINT_LAYOUT,
        )

    bind_route(app, "/print/<doc_type>/<int:item_id>", "print_document", print_document, ["GET"])
