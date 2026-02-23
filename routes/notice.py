"""공지사항 블루프린트 — 퍼블릭 + 관리자 CRUD."""

import logging

from flask import Blueprint, jsonify, render_template, request

from models import Announcement, db
from routes.utils import require_admin

logger = logging.getLogger(__name__)

notice_bp = Blueprint("notice", __name__)


# ── 퍼블릭 ──


@notice_bp.route("/notices")
def public_notices():
    notices = Announcement.query.filter_by(category="public").order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc(),
    ).all()
    return render_template("notices.html", notices=notices)


@notice_bp.route("/notices/<int:notice_id>")
def public_notice_detail(notice_id):
    notice = db.session.get(Announcement, notice_id)
    if not notice or notice.category != "public":
        return render_template("notice_detail.html", notice=None), 404
    return render_template("notice_detail.html", notice=notice)


@notice_bp.route("/api/notices/new")
def check_new_notices():
    last_seen = request.args.get("last_seen_id", 0, type=int)
    latest = Announcement.query.filter(
        Announcement.category == "public",
        Announcement.id > last_seen,
    ).order_by(Announcement.id.desc()).first()
    if latest:
        return jsonify({"has_new": True, "latest_id": latest.id, "title": latest.title})
    return jsonify({"has_new": False})


# ── 관리자 ──


@notice_bp.route("/admin/notices")
@require_admin
def admin_notices():
    notices = Announcement.query.order_by(
        Announcement.is_pinned.desc(),
        Announcement.created_at.desc(),
    ).all()
    return render_template("admin_notices.html", notices=notices)


@notice_bp.route("/api/notices", methods=["POST"])
@require_admin
def create_notice():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    title = str(data.get("title", "")).strip()
    content = str(data.get("content", "")).strip()
    category = str(data.get("category", "public")).strip()
    is_pinned = bool(data.get("is_pinned", False))

    if not title:
        return jsonify({"error": "제목을 입력해주세요."}), 400
    if not content:
        return jsonify({"error": "내용을 입력해주세요."}), 400
    if category not in ("public", "internal"):
        return jsonify({"error": "카테고리는 public 또는 internal 이어야 합니다."}), 400

    try:
        notice = Announcement(
            title=title,
            content=content,
            category=category,
            is_pinned=is_pinned,
        )
        db.session.add(notice)
        db.session.commit()
        return jsonify({"success": True, "notice": notice.to_dict()}), 201
    except Exception as exc:
        db.session.rollback()
        logger.error("Notice create error: %s", exc)
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


@notice_bp.route("/api/notices/<int:notice_id>", methods=["PUT"])
@require_admin
def update_notice(notice_id):
    notice = db.session.get(Announcement, notice_id)
    if not notice:
        return jsonify({"error": "공지를 찾을 수 없습니다."}), 404

    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "JSON body required"}), 400

    try:
        if "title" in data:
            title = str(data["title"]).strip()
            if not title:
                return jsonify({"error": "제목을 입력해주세요."}), 400
            notice.title = title

        if "content" in data:
            content = str(data["content"]).strip()
            if not content:
                return jsonify({"error": "내용을 입력해주세요."}), 400
            notice.content = content

        if "category" in data:
            category = str(data["category"]).strip()
            if category not in ("public", "internal"):
                return jsonify({"error": "카테고리는 public 또는 internal 이어야 합니다."}), 400
            notice.category = category

        if "is_pinned" in data:
            notice.is_pinned = bool(data["is_pinned"])

        db.session.commit()
        return jsonify({"success": True, "notice": notice.to_dict()})
    except Exception as exc:
        db.session.rollback()
        logger.error("Notice update error: %s", exc)
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500


@notice_bp.route("/api/notices/<int:notice_id>", methods=["DELETE"])
@require_admin
def delete_notice(notice_id):
    notice = db.session.get(Announcement, notice_id)
    if not notice:
        return jsonify({"error": "공지를 찾을 수 없습니다."}), 404

    try:
        db.session.delete(notice)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as exc:
        db.session.rollback()
        logger.error("Notice delete error: %s", exc)
        return jsonify({"error": "서버 오류가 발생했습니다."}), 500
