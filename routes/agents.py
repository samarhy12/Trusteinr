from datetime import datetime, date
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, abort, current_app
from flask_login import login_required, current_user

from extensions import db
from models import Staff, Repayment, Loan, CashTransaction, generate_transaction_id, is_business_day_open
from pagination_utils import paginate_items

bp = Blueprint("agents", __name__, url_prefix="/agents")


def can_record_repayments_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.can_record_repayments:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


@bp.route("/")
@login_required
def list_agents():
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    agents_all = Staff.query.filter_by(role="agent").order_by(Staff.full_name.asc()).all()
    pagination = paginate_items(agents_all, page, per_page)

    today = date.today()
    agent_today_totals = {}
    for agent in pagination.items:
        total = sum(
            r.amount for r in Repayment.query.filter_by(agent_id=agent.id, date=today).all()
        )
        agent_today_totals[agent.id] = round(total, 2)

    return render_template(
        "agents/list.html",
        agents=pagination.items,
        agent_today_totals=agent_today_totals,
        today=today,
        pagination=pagination,
        query_params={},
    )


@bp.route("/<int:agent_id>")
@login_required
def agent_detail(agent_id):
    agent = Staff.query.filter_by(id=agent_id, role="agent").first_or_404()

    view = request.args.get("view", "day")  # "day" or "all"
    date_str = request.args.get("date", "")

    if view == "all":
        repayments = Repayment.query.filter_by(agent_id=agent.id).order_by(Repayment.date.desc()).all()
        selected_date = None
    else:
        try:
            selected_date = datetime.strptime(date_str, "%Y-%m-%d").date() if date_str else date.today()
        except ValueError:
            selected_date = date.today()
        repayments = (
            Repayment.query.filter_by(agent_id=agent.id, date=selected_date)
            .order_by(Repayment.created_at.asc()).all()
        )

    total = round(sum(r.amount for r in repayments), 2)

    return render_template(
        "agents/detail.html",
        agent=agent,
        repayments=repayments,
        total=total,
        view=view,
        selected_date=selected_date,
        today=date.today(),
    )


@bp.route("/<int:agent_id>/record_payment", methods=["GET", "POST"])
@login_required
@can_record_repayments_required
def record_agent_payment(agent_id):
    agent = Staff.query.filter_by(id=agent_id, role="agent").first_or_404()
    
    if request.method == "POST":
        if not is_business_day_open():
            flash("The business day is closed. Open the day before recording payments.", "error")
            return redirect(url_for("agents.record_agent_payment", agent_id=agent_id))
        
        form = request.form
        errors = []
        
        loan_id = form.get("loan_id", type=int)
        amount_raw = form.get("amount", "").strip()
        date_raw = form.get("date", "").strip()
        note = form.get("note", "").strip() or None
        
        loan = Loan.query.get(loan_id) if loan_id else None
        if not loan:
            errors.append("Please select a valid loan.")
        elif loan.status != "active":
            errors.append(f"Loan {loan.loan_code} is not active. Only active loans can accept repayments.")
        
        try:
            amount = float(amount_raw)
            if amount <= 0:
                errors.append("Repayment amount must be greater than zero.")
        except ValueError:
            amount = None
            errors.append("Repayment amount must be a number.")
        
        try:
            pay_date = datetime.strptime(date_raw, "%Y-%m-%d").date() if date_raw else date.today()
        except ValueError:
            pay_date = date.today()
            errors.append("Payment date is not valid.")
        
        if amount is not None and loan and amount > loan.outstanding_balance + 0.01:
            errors.append(
                f"Amount exceeds outstanding balance of GHS {loan.outstanding_balance:,.2f}."
            )
        
        if errors:
            for e in errors:
                flash(e, "error")
            # Get active loans for the form
            active_loans = Loan.query.filter_by(status="active").order_by(Loan.created_at.desc()).all()
            return render_template("agents/record_payment.html", agent=agent, active_loans=active_loans, 
                                    form=form, today=date.today().isoformat())
        
        repayment = Repayment(
            loan_id=loan.id,
            transaction_id=generate_transaction_id(loan.customer, pay_date),
            amount=amount,
            date=pay_date,
            note=note,
            agent_id=agent.id,
            recorded_by_id=current_user.id,
        )
        db.session.add(repayment)
        db.session.flush()
        
        tx = CashTransaction(
            tx_type="repayment",
            amount=abs(amount),
            description=f"Repayment from {loan.customer.full_name} ({loan.loan_code}) — collected by {agent.full_name}",
            loan_id=loan.id,
            customer_id=loan.customer_id,
            staff_id=current_user.id,
            date=pay_date,
        )
        db.session.add(tx)
        
        loan.refresh_status()
        db.session.commit()
        
        flash(f"Repayment of GHS {amount:,.2f} recorded for {agent.full_name}.", "success")
        return redirect(url_for("agents.agent_detail", agent_id=agent.id))
    
    # GET request - show the form
    active_loans = Loan.query.filter_by(status="active").order_by(Loan.created_at.desc()).all()
    return render_template("agents/record_payment.html", agent=agent, active_loans=active_loans, 
                            form={}, today=date.today().isoformat())
