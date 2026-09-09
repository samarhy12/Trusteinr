from datetime import datetime, date
from functools import wraps

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, abort
from flask_login import login_required, current_user

from extensions import db
from models import (
    Customer, Loan, Repayment, CashTransaction, Guarantor, Staff, Notification, LoanReversalLog,
    subtract_years, is_business_day_open, generate_transaction_id,
)
from image_utils import validate_and_save_image
from pagination_utils import paginate_items

bp = Blueprint("loans", __name__, url_prefix="/loans")

TERM_TYPES = ("daily", "weekly", "monthly")
DURATION_UNIT_LABEL = {"daily": "days", "weekly": "weeks", "monthly": "months"}


def can_disburse_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.can_disburse_loans:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def can_record_repayments_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.can_record_repayments:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def can_reverse_loans_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not current_user.can_reverse_loans:
            abort(403)
        return view(*args, **kwargs)
    return wrapped


def max_allowed_dob():
    min_age = current_app.config["MINIMUM_CUSTOMER_AGE"]
    return subtract_years(date.today(), min_age)


def _save_photo(file_storage, prefix):
    return validate_and_save_image(
        file_storage, prefix,
        current_app.config["UPLOAD_FOLDER"], current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
    )


def _resolve_interest_rate(form, errors):
    """Standard preset (from config) or a custom admin-entered percentage."""
    choice = form.get("interest_choice", "standard")
    if choice == "custom":
        raw = form.get("custom_interest_rate", "").strip()
        try:
            pct = float(raw)
            if pct <= 0 or pct > 100:
                errors.append("Custom interest rate must be a percentage between 0 and 100.")
                return None
            return round(pct / 100.0, 4)
        except ValueError:
            errors.append("Custom interest rate must be a number.")
            return None
    return current_app.config["MONTHLY_INTEREST_RATE"]


@bp.route("/")
@login_required
def list_loans():
    status_filter = request.args.get("status", "active")
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    query = Loan.query
    loans_all = query.order_by(Loan.created_at.desc()).all()

    if status_filter == "overdue":
        loans_all = [l for l in loans_all if l.is_overdue]
    elif status_filter in ("active", "completed"):
        loans_all = [l for l in loans_all if l.status == status_filter and not (status_filter == "active" and l.is_overdue)]
    elif status_filter == "cancelled":
        loans_all = [l for l in loans_all if l.status == "cancelled"]

    pagination = paginate_items(loans_all, page, per_page)
    
    # Calculate summary statistics
    all_loans = Loan.query.all()
    active_loans = [l for l in all_loans if l.status == "active"]
    overdue_loans = [l for l in all_loans if l.is_overdue]
    completed_loans = [l for l in all_loans if l.status == "completed"]
    cancelled_loans = [l for l in all_loans if l.status == "cancelled"]
    
    total_outstanding = sum(l.outstanding_balance for l in active_loans)
    total_overdue = sum(l.outstanding_balance for l in overdue_loans)
    total_principal = sum(l.principal for l in active_loans)
    total_repayable = sum(l.total_repayable for l in active_loans)
    
    stats = {
        "total_loans": len(all_loans),
        "active_loans": len(active_loans),
        "overdue_loans": len(overdue_loans),
        "completed_loans": len(completed_loans),
        "cancelled_loans": len(cancelled_loans),
        "total_outstanding": total_outstanding,
        "total_overdue": total_overdue,
        "total_principal": total_principal,
        "total_repayable": total_repayable,
    }
    
    return render_template(
        "loans/list.html",
        loans=pagination.items,
        status_filter=status_filter,
        pagination=pagination,
        query_params={"status": status_filter} if status_filter != "all" else {},
        stats=stats,
    )


@bp.route("/due")
@login_required
def due_loans():
    """Show loans with payments due today and overdue payments."""
    today = date.today()
    
    # Get all active loans
    active_loans = Loan.query.filter_by(status="active").all()
    
    # Categorize loans
    due_today = []
    overdue = []
    
    for loan in active_loans:
        if loan.is_payment_due_today:
            due_today.append(loan)
        elif loan.is_payment_overdue:
            overdue.append(loan)
    
    # Sort by due date and then by amount overdue
    due_today.sort(key=lambda l: (l.next_due_date, l.outstanding_balance))
    overdue.sort(key=lambda l: (l.overdue_days, l.outstanding_balance), reverse=True)
    
    return render_template(
        "loans/due.html",
        due_today=due_today,
        overdue=overdue,
        today=today,
    )


@bp.route("/due/notify", methods=["POST"])
@login_required
def send_due_notification():
    """Send notification about due loans to admins and agents."""
    if not current_user.is_admin:
        abort(403)
    
    today = date.today()
    
    # Get all active loans
    active_loans = Loan.query.filter_by(status="active").all()
    
    # Categorize loans
    due_today = []
    overdue = []
    
    for loan in active_loans:
        if loan.is_payment_due_today:
            due_today.append(loan)
        elif loan.is_payment_overdue:
            overdue.append(loan)
    
    if not due_today and not overdue:
        flash("No due or overdue loans to notify about.", "error")
        return redirect(url_for("loans.due_loans"))
    
    # Create notification content
    due_count = len(due_today)
    overdue_count = len(overdue)
    total_due_amount = sum(l.installment_amount for l in due_today)
    total_overdue_amount = sum(l.installment_amount for l in overdue)
    
    title = f"Loan Payment Collection Alert - {today.strftime('%d %b %Y')}"
    message = f"""
Payment Collection Report for {today.strftime('%d %b %Y')}

DUE TODAY ({due_count} loans):
• Total amount due: GHS {total_due_amount:,.2f}
• Customers with payments due today

OVERDUE ({overdue_count} loans):
• Total overdue amount: GHS {total_overdue_amount:,.2f}
• Customers with overdue payments

Please follow up with customers for payment collection.
"""
    
    # Store loan data in loan_data field
    notification_data = {
        "due_today": [
            {
                "loan_id": l.id,
                "loan_code": l.loan_code,
                "customer_name": l.customer.full_name,
                "customer_phone": l.customer.phone_number,
                "amount": l.installment_amount,
                "due_date": l.next_due_date.isoformat() if l.next_due_date else None
            } for l in due_today
        ],
        "overdue": [
            {
                "loan_id": l.id,
                "loan_code": l.loan_code,
                "customer_name": l.customer.full_name,
                "customer_phone": l.customer.phone_number,
                "amount": l.installment_amount,
                "days_overdue": l.overdue_days,
                "due_date": l.next_due_date.isoformat() if l.next_due_date else None
            } for l in overdue
        ],
        "summary": {
            "due_count": due_count,
            "overdue_count": overdue_count,
            "total_due_amount": total_due_amount,
            "total_overdue_amount": total_overdue_amount,
            "date": today.isoformat()
        }
    }
    
    # Send notifications to all admins and office staff
    recipients = Staff.query.filter(
        Staff.role.in_(["admin", "office_staff"]),
        Staff.is_active_staff == True
    ).all()
    
    notifications_sent = 0
    for recipient in recipients:
        notification = Notification(
            title=title,
            message=message,
            notification_type="due_loans",
            recipient_id=recipient.id,
            recipient_role=None,  # Specific recipient
            loan_data=notification_data
        )
        db.session.add(notification)
        notifications_sent += 1
    
    db.session.commit()
    
    flash(f"Notification sent to {notifications_sent} staff members about {due_count} due and {overdue_count} overdue loans.", "success")
    return redirect(url_for("loans.due_loans"))


@bp.route("/new", methods=["GET", "POST"])
@login_required
@can_disburse_required
def new_loan():
    customer_id = request.args.get("customer_id", type=int)
    customers = Customer.query.order_by(Customer.full_name).all()
    id_types = ["Ghana Card", "Voter's ID", "Driver's License", "Passport", "NHIS Card"]
    employment_statuses = ["Employed", "Self-employed", "Unemployed", "Student", "Retired"]
    genders = ["Male", "Female"]
    relationships = ["Spouse", "Parent", "Sibling", "Child", "Friend", "Colleague", "Relative", "Other"]
    standard_rate_pct = current_app.config["MONTHLY_INTEREST_RATE"] * 100

    # Find previous guarantor for repeat customers
    previous_guarantor = None
    previous_guarantor_type = None
    if customer_id:
        customer = Customer.query.get(customer_id)
        if customer:
            # Find the most recent completed loan for this customer
            previous_loan = Loan.query.filter_by(customer_id=customer.id, status="completed") \
                .order_by(Loan.created_at.desc()).first()
            if previous_loan:
                if previous_loan.guarantor_customer_id:
                    previous_guarantor = Customer.query.get(previous_loan.guarantor_customer_id)
                    previous_guarantor_type = "existing"
                elif previous_loan.guarantor_id:
                    previous_guarantor = Guarantor.query.get(previous_loan.guarantor_id)
                    previous_guarantor_type = "new"

    if request.method == "POST":
        if not is_business_day_open():
            flash("The business day is closed. Open the day before disbursing loans.", "error")
            return redirect(url_for("loans.new_loan"))

        form = request.form
        errors = []

        cid = form.get("customer_id", type=int)
        principal_raw = form.get("principal", "").strip()
        term_type = form.get("term_type")
        duration_raw = form.get("duration_value", "").strip()
        start_date_raw = form.get("start_date", "").strip()
        guarantor_type = form.get("guarantor_type", "existing")

        customer = Customer.query.get(cid) if cid else None
        if not customer:
            errors.append("Please select a valid customer.")
        else:
            existing_active = Loan.query.filter_by(customer_id=customer.id, status="active").first()
            if existing_active:
                errors.append(
                    f"{customer.full_name} already has an active loan "
                    f"({existing_active.loan_code}) and cannot be given another until it is completed."
                )
            
            # Recalculate previous guarantor for form validation error case
            previous_loan = Loan.query.filter_by(customer_id=customer.id, status="completed") \
                .order_by(Loan.created_at.desc()).first()
            if previous_loan:
                if previous_loan.guarantor_customer_id:
                    previous_guarantor = Customer.query.get(previous_loan.guarantor_customer_id)
                    previous_guarantor_type = "existing"
                elif previous_loan.guarantor_id:
                    previous_guarantor = Guarantor.query.get(previous_loan.guarantor_id)
                    previous_guarantor_type = "new"

        try:
            principal = float(principal_raw)
            if principal <= 0:
                errors.append("Loan amount must be greater than zero.")
        except ValueError:
            principal = None
            errors.append("Loan amount must be a number.")

        if term_type not in TERM_TYPES:
            errors.append("Please choose a valid repayment term.")

        try:
            duration_value = int(duration_raw)
            if duration_value <= 0:
                errors.append("Loan duration must be greater than zero.")
        except ValueError:
            duration_value = None
            errors.append(f"Please enter the number of {DURATION_UNIT_LABEL.get(term_type, 'periods')} for this loan.")

        rate = _resolve_interest_rate(form, errors)

        try:
            start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date() if start_date_raw else date.today()
        except ValueError:
            errors.append("Start date is not valid.")
            start_date = date.today()

        # ---- Guarantor ----
        guarantor_customer = None
        new_guarantor_data = None
        if guarantor_type == "existing":
            gid = form.get("guarantor_customer_id", type=int)
            guarantor_customer = Customer.query.get(gid) if gid else None
            if not guarantor_customer:
                errors.append("Please select a guarantor from the customer list.")
            elif customer and guarantor_customer.id == customer.id:
                errors.append("The guarantor cannot be the same person as the borrower.")
        else:
            g_name = form.get("guarantor_full_name", "").strip()
            g_gender = form.get("guarantor_gender", "")
            g_dob_raw = form.get("guarantor_date_of_birth", "").strip()
            g_id_type = form.get("guarantor_id_type", "")
            g_id_number = form.get("guarantor_id_number", "").strip()
            g_phone = form.get("guarantor_phone_number", "").strip()
            g_address = form.get("guarantor_residential_address", "").strip()
            g_occupation = form.get("guarantor_occupation", "").strip()
            g_employment = form.get("guarantor_employment_status", "")
            g_business = form.get("guarantor_business_type", "").strip() or None
            g_relationship = form.get("guarantor_relationship_to_customer", "").strip()

            required_g = [g_name, g_gender, g_dob_raw, g_id_type, g_id_number, g_phone, g_address, g_occupation, g_employment]
            if not all(required_g):
                errors.append("Please complete all required guarantor details.")
            
            if not g_relationship:
                errors.append("Please specify the guarantor's relationship to the customer.")

            g_dob = None
            if g_dob_raw:
                try:
                    g_dob = datetime.strptime(g_dob_raw, "%Y-%m-%d").date()
                    if g_dob > max_allowed_dob():
                        errors.append("The guarantor must be at least 18 years old.")
                except ValueError:
                    errors.append("Guarantor date of birth is not valid.")

            new_guarantor_data = dict(
                full_name=g_name, gender=g_gender, date_of_birth=g_dob, id_type=g_id_type,
                id_number=g_id_number, phone_number=g_phone, residential_address=g_address,
                occupation=g_occupation, employment_status=g_employment, business_type=g_business,
                relationship_to_customer=g_relationship,
            )

            g_photo = request.files.get("guarantor_photo")
            if g_photo and g_photo.filename:
                ext = g_photo.filename.rsplit(".", 1)[-1].lower() if "." in g_photo.filename else ""
                if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
                    errors.append("Guarantor photo must be a PNG or JPG image.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("loans/form.html", customers=customers, form=form,
                                    selected_customer_id=cid, today=date.today().isoformat(),
                                    id_types=id_types, employment_statuses=employment_statuses, genders=genders,
                                    relationships=relationships,
                                    max_dob=max_allowed_dob().isoformat(), standard_rate_pct=standard_rate_pct,
                                    previous_guarantor=previous_guarantor, previous_guarantor_type=previous_guarantor_type)

        end_date, total_interest, total_repayable, installment, num_installments = Loan.compute_schedule(
            principal, rate, term_type, duration_value, start_date
        )

        loan = Loan(
            customer_id=customer.id,
            principal=principal,
            interest_rate=rate,
            duration_value=duration_value,
            term_type=term_type,
            start_date=start_date,
            end_date=end_date,
            total_interest=total_interest,
            total_repayable=total_repayable,
            installment_amount=installment,
            number_of_installments=num_installments,
            status="active",
            created_by_id=current_user.id,
        )

        if guarantor_type == "existing":
            loan.guarantor_customer_id = guarantor_customer.id
        else:
            guarantor = Guarantor(**new_guarantor_data)
            db.session.add(guarantor)
            db.session.flush()
            g_photo = request.files.get("guarantor_photo")
            if g_photo and g_photo.filename:
                filename = _save_photo(g_photo, f"guarantor-{guarantor.id}")
                if filename and filename != "__invalid__":
                    guarantor.photo_filename = filename
            loan.guarantor_id = guarantor.id

        db.session.add(loan)
        db.session.flush()  # get loan.id

        tx = CashTransaction(
            tx_type="disbursement",
            amount=-abs(principal),
            description=f"Loan disbursement to {customer.full_name} ({loan.loan_code})",
            loan_id=loan.id,
            customer_id=customer.id,
            staff_id=current_user.id,
            date=start_date,
        )
        db.session.add(tx)
        db.session.commit()

        flash(f"Loan {loan.loan_code} of GHS {principal:,.2f} disbursed to {customer.full_name}.", "success")
        return redirect(url_for("loans.view_loan", loan_id=loan.id))

    return render_template("loans/form.html", customers=customers, form={},
                            selected_customer_id=customer_id, today=date.today().isoformat(),
                            id_types=id_types, employment_statuses=employment_statuses, genders=genders,
                            relationships=relationships,
                            max_dob=max_allowed_dob().isoformat(), standard_rate_pct=standard_rate_pct,
                            previous_guarantor=previous_guarantor, previous_guarantor_type=previous_guarantor_type)


@bp.route("/previous-guarantor/<int:customer_id>")
@login_required
def get_previous_guarantor(customer_id):
    """AJAX endpoint: Get previous guarantor for a customer with completed loans."""
    customer = Customer.query.get_or_404(customer_id)
    
    # Find the most recent completed loan for this customer
    previous_loan = Loan.query.filter_by(customer_id=customer.id, status="completed") \
        .order_by(Loan.created_at.desc()).first()
    
    if not previous_loan:
        return jsonify({"has_previous": False})
    
    guarantor_data = None
    guarantor_type = None
    
    if previous_loan.guarantor_customer_id:
        guarantor = Customer.query.get(previous_loan.guarantor_customer_id)
        if guarantor:
            guarantor_data = {
                "id": guarantor.id,
                "full_name": guarantor.full_name,
                "customer_code": guarantor.customer_code
            }
            guarantor_type = "existing"
    elif previous_loan.guarantor_id:
        guarantor = Guarantor.query.get(previous_loan.guarantor_id)
        if guarantor:
            guarantor_data = {
                "full_name": guarantor.full_name,
                "gender": guarantor.gender,
                "date_of_birth": guarantor.date_of_birth.isoformat() if guarantor.date_of_birth else None,
                "phone_number": guarantor.phone_number,
                "id_type": guarantor.id_type,
                "id_number": guarantor.id_number,
                "residential_address": guarantor.residential_address,
                "occupation": guarantor.occupation,
                "employment_status": guarantor.employment_status,
                "business_type": guarantor.business_type,
                "relationship_to_customer": guarantor.relationship_to_customer
            }
            guarantor_type = "new"
    
    return jsonify({
        "has_previous": True,
        "guarantor_type": guarantor_type,
        "guarantor": guarantor_data
    })


@bp.route("/preview")
@login_required
def preview_schedule():
    """AJAX endpoint: live-preview loan schedule as the officer fills the form."""
    try:
        principal = float(request.args.get("principal", 0))
    except ValueError:
        principal = 0
    term_type = request.args.get("term_type", "monthly")
    start_date_raw = request.args.get("start_date", "")

    try:
        duration_value = int(request.args.get("duration_value", 0))
    except ValueError:
        duration_value = 0

    try:
        rate_pct = float(request.args.get("rate_pct", 0))
    except ValueError:
        rate_pct = 0

    try:
        start_date = datetime.strptime(start_date_raw, "%Y-%m-%d").date() if start_date_raw else date.today()
    except ValueError:
        start_date = date.today()

    if principal <= 0 or term_type not in TERM_TYPES or duration_value <= 0 or rate_pct <= 0:
        return jsonify({"ok": False})

    rate = rate_pct / 100.0

    end_date, total_interest, total_repayable, installment, num_installments = Loan.compute_schedule(
        principal, rate, term_type, duration_value, start_date
    )

    return jsonify({
        "ok": True,
        "end_date": end_date.strftime("%d %b %Y"),
        "total_interest": f"{total_interest:,.2f}",
        "total_repayable": f"{total_repayable:,.2f}",
        "installment": f"{installment:,.2f}",
        "num_installments": num_installments,
    })


@bp.route("/<int:loan_id>")
@login_required
def view_loan(loan_id):
    loan = Loan.query.get_or_404(loan_id)
    loan.refresh_status()
    db.session.commit()
    repayments = loan.repayments.order_by(Repayment.date.desc()).all()
    agents = Staff.query.filter_by(role="agent", is_active_staff=True).order_by(Staff.full_name).all()
    return render_template("loans/view.html", loan=loan, repayments=repayments, today=date.today(), agents=agents)


@bp.route("/<int:loan_id>/repayments/<int:repayment_id>/receipt")
@login_required
def repayment_receipt(loan_id, repayment_id):
    loan = Loan.query.get_or_404(loan_id)
    repayment = Repayment.query.filter_by(id=repayment_id, loan_id=loan.id).first_or_404()

    # Balance as it stood right after THIS receipt was issued — not the loan's
    # current balance, which may have moved on if later repayments were made since.
    all_repayments = loan.repayments.order_by(Repayment.date.asc(), Repayment.created_at.asc()).all()
    paid_up_to_this_one = 0.0
    for r in all_repayments:
        paid_up_to_this_one += r.amount
        if r.id == repayment.id:
            break
    balance_after = round(loan.total_repayable - paid_up_to_this_one, 2)
    balance_before = round(balance_after + repayment.amount, 2)

    return render_template("loans/receipt.html", loan=loan, repayment=repayment,
                            balance_before=balance_before, balance_after=balance_after)


@bp.route("/repayments")
@login_required
def list_repayments():
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    repayments_all = Repayment.query.order_by(Repayment.date.desc(), Repayment.created_at.desc()).all()
    pagination = paginate_items(repayments_all, page, per_page)
    return render_template(
        "loans/repayments.html",
        repayments=pagination.items,
        pagination=pagination,
        query_params={},
    )


@bp.route("/transactions/search")
@login_required
def search_transaction():
    query = request.args.get("q", "").strip()
    repayment = None
    searched = bool(query)

    if query:
        repayment = Repayment.query.filter_by(transaction_id=query).first()
        if repayment is None:
            # Be forgiving of accidental spaces/case on manual entry.
            repayment = Repayment.query.filter(
                db.func.lower(Repayment.transaction_id) == query.lower()
            ).first()

    return render_template("loans/search_transaction.html", query=query, repayment=repayment, searched=searched)


@bp.route("/<int:loan_id>/repay", methods=["POST"])
@login_required
@can_record_repayments_required
def record_repayment(loan_id):
    if not is_business_day_open():
        flash("The business day is closed. Open the day before recording repayments.", "error")
        return redirect(url_for("loans.view_loan", loan_id=loan_id))

    loan = Loan.query.get_or_404(loan_id)
    amount_raw = request.form.get("amount", "").strip()
    date_raw = request.form.get("date", "").strip()
    note = request.form.get("note", "").strip() or None
    agent_id = request.form.get("agent_id", type=int)

    errors = []
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

    agent = Staff.query.filter_by(id=agent_id, role="agent").first() if agent_id else None
    if not agent:
        errors.append("Please select which agent collected this payment.")

    if amount is not None and amount > loan.outstanding_balance + 0.01:
        errors.append(
            f"Amount exceeds outstanding balance of GHS {loan.outstanding_balance:,.2f}."
        )

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("loans.view_loan", loan_id=loan.id))

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
    return redirect(url_for("loans.repayment_receipt", loan_id=loan.id, repayment_id=repayment.id))


@bp.route("/<int:loan_id>/reverse", methods=["GET", "POST"])
@login_required
@can_reverse_loans_required
def reverse_loan(loan_id):
    """Reverse a mistakenly disbursed loan with multiple safeguards."""
    loan = Loan.query.get_or_404(loan_id)

    # Multi-layer safeguards
    errors = []

    # 1. Check if loan can be reversed (no repayments allowed)
    if not loan.can_be_reversed:
        if loan.status != "active":
            errors.append(f"Cannot reverse loan with status '{loan.status}'. Only active loans can be reversed.")
        elif loan.amount_paid > 0:
            errors.append(f"Cannot reverse loan with repayments. This loan has GHS {loan.amount_paid:,.2f} already paid.")

    # 2. Check if business day is open
    if not is_business_day_open():
        errors.append("The business day is closed. Loan reversals can only be performed when the business day is open.")

    if errors:
        for e in errors:
            flash(e, "error")
        return redirect(url_for("loans.view_loan", loan_id=loan.id))

    if request.method == "POST":
        # 3. Password re-authentication
        password = request.form.get("password", "")
        if not current_user.check_password(password):
            flash("Incorrect password. Please re-enter your password to confirm the reversal.", "error")
            return render_template("loans/reverse_confirm.html", loan=loan)

        # 4. Explicit reason requirement
        reason = request.form.get("reason", "").strip()
        if not reason or len(reason) < 10:
            flash("Please provide a detailed reason for the reversal (at least 10 characters).", "error")
            return render_template("loans/reverse_confirm.html", loan=loan, reason=reason)

        # 5. Final confirmation
        confirm = request.form.get("confirm")
        if confirm != "REVERSE":
            flash("Please type 'REVERSE' to confirm this action.", "error")
            return render_template("loans/reverse_confirm.html", loan=loan, reason=reason)

        # Perform the reversal
        try:
            # Find and delete the disbursement cash transaction
            disbursement_tx = CashTransaction.query.filter_by(
                loan_id=loan.id,
                tx_type="disbursement"
            ).first()

            if disbursement_tx:
                db.session.delete(disbursement_tx)

            # Create reversal cash transaction to restore the cash
            reversal_tx = CashTransaction(
                tx_type="reversal",
                amount=abs(loan.principal),  # Positive amount to restore cash
                description=f"Loan reversal: {loan.loan_code} - {loan.customer.full_name}",
                loan_id=loan.id,
                customer_id=loan.customer_id,
                staff_id=current_user.id,
                date=date.today(),
            )
            db.session.add(reversal_tx)

            # Update loan status and reversal tracking
            loan.status = "cancelled"
            loan.reversed_at = datetime.now()
            loan.reversed_by_id = current_user.id
            loan.reversal_reason = reason

            # Create audit log
            ip_address = request.remote_addr or None

            reversal_log = LoanReversalLog(
                loan_id=loan.id,
                loan_code=loan.loan_code,
                customer_id=loan.customer_id,
                customer_name=loan.customer.full_name,
                principal_amount=loan.principal,
                reversed_by_id=current_user.id,
                reversed_by_name=current_user.full_name,
                reason=reason,
                ip_address=ip_address,
            )
            db.session.add(reversal_log)

            db.session.commit()

            flash(f"Loan {loan.loan_code} has been successfully reversed. Cash ledger has been restored.", "success")
            return redirect(url_for("loans.view_loan", loan_id=loan.id))

        except Exception as e:
            db.session.rollback()
            flash(f"Error reversing loan: {str(e)}", "error")
            return redirect(url_for("loans.view_loan", loan_id=loan.id))

    return render_template("loans/reverse_confirm.html", loan=loan)
