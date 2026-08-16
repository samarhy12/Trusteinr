from datetime import datetime
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_login import login_required, current_user

from extensions import db
from models import Notification, Staff
from pagination_utils import paginate_items

bp = Blueprint("notifications", __name__, url_prefix="/notifications")


@bp.route("/")
@login_required
def list_notifications():
    """Show notifications for the current user."""
    page = request.args.get("page", 1, type=int)
    per_page = 20
    
    # Get notifications for current user (by ID or role)
    query = Notification.query.filter(
        (Notification.recipient_id == current_user.id) |
        (Notification.recipient_role == current_user.role) |
        (Notification.recipient_role == "all")
    ).order_by(Notification.created_at.desc())
    
    notifications_all = query.all()
    pagination = paginate_items(notifications_all, page, per_page)
    
    # Mark notifications as read when viewed
    unread_notifications = [n for n in pagination.items if not n.is_read]
    for notification in unread_notifications:
        notification.is_read = True
        notification.read_at = datetime.now()
    
    if unread_notifications:
        db.session.commit()
    
    return render_template(
        "notifications/list.html",
        notifications=pagination.items,
        pagination=pagination,
        query_params={},
    )


@bp.route("/<int:notification_id>")
@login_required
def view_notification(notification_id):
    """View a specific notification and its details."""
    notification = Notification.query.get_or_404(notification_id)
    
    # Check if user has permission to view this notification
    if (notification.recipient_id and notification.recipient_id != current_user.id and
        not current_user.is_admin):
        abort(403)
    if (notification.recipient_role and notification.recipient_role != current_user.role and
        notification.recipient_role != "all" and not current_user.is_admin):
        abort(403)
    
    # Mark as read if not already
    if not notification.is_read:
        notification.is_read = True
        notification.read_at = datetime.now()
        db.session.commit()
    
    return render_template(
        "notifications/view.html",
        notification=notification,
    )


@bp.route("/<int:notification_id>/print")
@login_required
def print_notification(notification_id):
    """Print a notification with detailed loan information."""
    notification = Notification.query.get_or_404(notification_id)
    
    # Check if user has permission to view this notification
    if (notification.recipient_id and notification.recipient_id != current_user.id and
        not current_user.is_admin):
        abort(403)
    if (notification.recipient_role and notification.recipient_role != current_user.role and
        notification.recipient_role != "all" and not current_user.is_admin):
        abort(403)
    
    return render_template(
        "notifications/print.html",
        notification=notification,
    )