from __future__ import annotations

from datetime import datetime

from flask import abort, flash, redirect, render_template, request, send_from_directory, url_for
from werkzeug.utils import secure_filename

from fabouanes.config import BASE_DIR
from fabouanes.core.decorators import login_required
from fabouanes.core.storage import PDF_READER_DIR, ensure_runtime_dirs
from fabouanes.routes.route_utils import bind_route
from fabouanes.runtime_app import list_notes_history, notes_file_path, read_app_notes, read_notes_version, write_app_notes


def register_tools_routes(app):
    def service_worker():
        return send_from_directory(BASE_DIR / "static", "sw.js", mimetype="application/javascript")

    @login_required
    def notes_page():
        if request.method == "POST":
            action = request.form.get("action", "save")
            if action == "restore":
                filename = request.form.get("version_file", "")
                restored = read_notes_version(filename) if filename else ""
                if restored:
                    write_app_notes(restored)
                    flash("Version restauree avec succes.", "success")
                else:
                    flash("Version introuvable.", "danger")
            else:
                write_app_notes(request.form.get("content", ""))
                flash("Bloc-note enregistre.", "success")
            return redirect(url_for("notes_page"))

        view_version = request.args.get("v", "")
        viewing_content = read_notes_version(view_version) if view_version else read_app_notes()
        current_path = notes_file_path()
        updated_at = None
        if current_path.exists():
            updated_at = datetime.fromtimestamp(current_path.stat().st_mtime).strftime("%d/%m/%Y %H:%M")
        return render_template(
            "notes.html",
            content=viewing_content,
            current_content=read_app_notes(),
            updated_at=updated_at,
            history=list_notes_history(),
            view_version=view_version,
        )

    @login_required
    def pdf_reader():
        ensure_runtime_dirs()
        if request.method == "POST":
            if request.form.get("action", "upload") == "delete":
                filename = secure_filename(request.form.get("filename", ""))
                target = PDF_READER_DIR / filename
                if filename and target.exists():
                    target.unlink()
                    flash(f"PDF supprime : {filename}", "success")
                else:
                    flash("Fichier introuvable.", "warning")
                return redirect(url_for("pdf_reader"))

            uploaded = request.files.get("pdf_file")
            if not uploaded or not uploaded.filename:
                flash("Choisis un fichier PDF.", "warning")
                return redirect(url_for("pdf_reader"))

            filename = secure_filename(uploaded.filename)
            if not filename.lower().endswith(".pdf"):
                flash("Seuls les fichiers PDF sont acceptes.", "danger")
                return redirect(url_for("pdf_reader"))

            uploaded.save(PDF_READER_DIR / filename)
            flash(f"PDF ajoute : {filename}", "success")
            return redirect(url_for("pdf_reader", file=filename))

        files = sorted([path.name for path in PDF_READER_DIR.glob("*.pdf")], key=str.lower)
        selected = request.args.get("file", "").strip()
        if selected and selected not in files:
            selected = ""
        return render_template("pdf_reader.html", files=files, selected=selected)

    @login_required
    def pdf_reader_file(filename: str):
        safe_name = secure_filename(filename)
        if not safe_name or not (PDF_READER_DIR / safe_name).exists():
            abort(404)
        return send_from_directory(PDF_READER_DIR, safe_name, mimetype="application/pdf", as_attachment=False)

    bind_route(app, "/sw.js", "service_worker", service_worker, ["GET"])
    bind_route(app, "/notes", "notes_page", notes_page, ["GET", "POST"])
    bind_route(app, "/pdf-reader", "pdf_reader", pdf_reader, ["GET", "POST"])
    bind_route(app, "/pdf-reader/file/<path:filename>", "pdf_reader_file", pdf_reader_file, ["GET"])
