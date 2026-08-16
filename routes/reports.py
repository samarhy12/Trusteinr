from datetime import date, datetime, timedelta

from flask import Blueprint, render_template, request
from flask_login import login_required

from extensions import db
from models import CashTransaction, Customer, Expense, Loan, Repayment

bp = Blueprint("reports", __name__, url_prefix="/reports")


@bp.route("/")
@login_required
def index():
    today = date.today()
    week_ago = today - timedelta(days=6)

    total_customers = Customer.query.count()
    active_loans = Loan.query.filter_by(status="active").count()
    overdue_loans = Loan.query.filter_by(status="active").all()
    overdue_count = sum(1 for loan in overdue_loans if loan.is_overdue)

    repayments_today = Repayment.query.filter_by(date=today).count()
    repayments_week = Repayment.query.filter(Repayment.date >= week_ago).count()
    expenses_week = Expense.query.filter(Expense.date >= week_ago).count()

    cash_in = db.session.query(db.func.coalesce(db.func.sum(CashTransaction.amount), 0.0)) \
        .filter(CashTransaction.tx_type == "repayment").scalar() or 0
    cash_out = db.session.query(db.func.coalesce(db.func.sum(CashTransaction.amount), 0.0)) \
        .filter(CashTransaction.tx_type.in_(["disbursement", "expense"])).scalar() or 0

    return render_template(
        "reports/index.html",
        today=today,
        total_customers=total_customers,
        active_loans=active_loans,
        overdue_count=overdue_count,
        repayments_today=repayments_today,
        repayments_week=repayments_week,
        expenses_week=expenses_week,
        cash_in=round(abs(cash_in or 0), 2),
        cash_out=round(abs(cash_out or 0), 2),
    )


@bp.route("/today-payments")
@login_required
def today_payments():
    today = date.today()
    q = request.args.get("q", "").strip()
    query = Repayment.query.filter_by(date=today)

    if q:
        like = f"%{q}%"
        query = query.join(Loan).join(Customer).filter(
            db.or_(
                Customer.full_name.ilike(like),
                Loan.loan_code.ilike(like),
                Repayment.transaction_id.ilike(like),
            )
        )

    repayments = query.order_by(Repayment.created_at.asc()).all()
    return render_template("reports/today_payments.html", repayments=repayments, today=today, q=q)
