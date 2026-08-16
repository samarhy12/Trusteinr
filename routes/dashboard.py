from datetime import date, timedelta

from flask import Blueprint, render_template
from flask_login import login_required, current_user

from extensions import db
from models import Customer, Loan, Repayment, CashTransaction, current_cash_in_hand, BusinessDay, is_weekend

bp = Blueprint("dashboard", __name__)


@bp.route("/system-closed")
def system_closed():
    return render_template("system_closed.html", is_weekend_today=is_weekend())


@bp.route("/")
@login_required
def index():
    cash_in_hand = current_cash_in_hand()

    total_customers = Customer.query.count()
    active_loans = Loan.query.filter_by(status="active").all()
    active_loans_count = len(active_loans)

    outstanding_total = round(sum(l.outstanding_balance for l in active_loans), 2)
    overdue_loans = [l for l in active_loans if l.is_overdue]

    today = date.today()
    week_ago = today - timedelta(days=7)

    today_row = BusinessDay.query.filter_by(date=today).first()
    business_day_open = bool(today_row and today_row.is_open)

    recent_repayments = Repayment.query.order_by(Repayment.created_at.desc()).limit(8).all()
    recent_transactions = CashTransaction.query.order_by(CashTransaction.created_at.desc()).limit(8).all()

    disbursed_this_week = db.session.query(db.func.coalesce(db.func.sum(CashTransaction.amount), 0.0)) \
        .filter(CashTransaction.tx_type == "disbursement", CashTransaction.date >= week_ago).scalar()
    collected_this_week = db.session.query(db.func.coalesce(db.func.sum(CashTransaction.amount), 0.0)) \
        .filter(CashTransaction.tx_type == "repayment", CashTransaction.date >= week_ago).scalar()
    expenses_this_week = db.session.query(db.func.coalesce(db.func.sum(CashTransaction.amount), 0.0)) \
        .filter(CashTransaction.tx_type == "expense", CashTransaction.date >= week_ago).scalar()

    total_disbursed_all_time = db.session.query(db.func.coalesce(db.func.sum(Loan.principal), 0.0)).scalar()
    total_collected_all_time = db.session.query(db.func.coalesce(db.func.sum(Repayment.amount), 0.0)).scalar()

    return render_template(
        "dashboard.html",
        cash_in_hand=cash_in_hand,
        total_customers=total_customers,
        active_loans_count=active_loans_count,
        outstanding_total=outstanding_total,
        overdue_loans=overdue_loans,
        recent_repayments=recent_repayments,
        recent_transactions=recent_transactions,
        disbursed_this_week=round(abs(disbursed_this_week or 0), 2),
        collected_this_week=round(collected_this_week or 0, 2),
        expenses_this_week=round(abs(expenses_this_week or 0), 2),
        total_disbursed_all_time=round(total_disbursed_all_time or 0, 2),
        total_collected_all_time=round(total_collected_all_time or 0, 2),
        business_day_open=business_day_open,
        is_weekend_today=is_weekend(today),
    )
