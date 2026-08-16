from datetime import datetime, date

from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, abort
from flask_login import login_required, current_user

from extensions import db
from models import Customer, Loan, Repayment, subtract_years, next_registration_number
from image_utils import validate_and_save_image, delete_upload
from pagination_utils import paginate_items

bp = Blueprint("customers", __name__, url_prefix="/customers")

ID_TYPES = ["Ghana Card", "Voter's ID", "Driver's License", "Passport", "NHIS Card"]
EMPLOYMENT_STATUSES = ["Employed", "Self-employed", "Unemployed", "Student", "Retired"]
GENDERS = ["Male", "Female"]


def max_allowed_dob():
    """The latest date of birth a customer can have to be at least the minimum age."""
    min_age = current_app.config["MINIMUM_CUSTOMER_AGE"]
    return subtract_years(date.today(), min_age)


def _save_photo(file_storage, customer_id):
    return validate_and_save_image(
        file_storage, f"customer-{customer_id}",
        current_app.config["UPLOAD_FOLDER"], current_app.config["ALLOWED_IMAGE_EXTENSIONS"],
    )


def _delete_photo(filename):
    delete_upload(filename, current_app.config["UPLOAD_FOLDER"])


@bp.route("/")
@login_required
def list_customers():
    q = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)
    per_page = current_app.config["DEFAULT_PAGE_SIZE"]
    query = Customer.query
    if q:
        like = f"%{q}%"
        query = query.filter(
            db.or_(
                Customer.full_name.ilike(like),
                Customer.phone_number.ilike(like),
                Customer.customer_code.ilike(like),
                Customer.id_number.ilike(like),
            )
        )
    customers_all = query.order_by(Customer.created_at.desc()).all()
    pagination = paginate_items(customers_all, page, per_page)
    return render_template(
        "customers/list.html",
        customers=pagination.items,
        q=q,
        pagination=pagination,
        query_params={"q": q} if q else {},
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required
def new_customer():
    if request.method == "POST":
        form = request.form
        errors = []

        required = ["full_name", "gender", "date_of_birth", "id_type", "id_number",
                    "phone_number", "residential_address", "occupation", "employment_status"]
        for field in required:
            if not form.get(field, "").strip():
                errors.append(f"{field.replace('_', ' ').title()} is required.")

        dob = None
        if form.get("date_of_birth"):
            try:
                dob = datetime.strptime(form.get("date_of_birth"), "%Y-%m-%d").date()
            except ValueError:
                errors.append("Date of birth is not valid.")

        min_age = current_app.config["MINIMUM_CUSTOMER_AGE"]
        if dob and dob > max_allowed_dob():
            errors.append(f"Customer must be at least {min_age} years old.")

        photo = request.files.get("photo")
        if photo and photo.filename:
            ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
            if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
                errors.append("Passport picture must be a PNG or JPG image.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("customers/form.html", form=form, id_types=ID_TYPES,
                                    employment_statuses=EMPLOYMENT_STATUSES, genders=GENDERS,
                                    max_dob=max_allowed_dob().isoformat())

        customer = Customer(
            registration_number=next_registration_number(),
            full_name=form.get("full_name").strip(),
            gender=form.get("gender"),
            date_of_birth=dob,
            id_type=form.get("id_type"),
            id_number=form.get("id_number").strip(),
            phone_number=form.get("phone_number").strip(),
            residential_address=form.get("residential_address").strip(),
            occupation=form.get("occupation").strip(),
            employment_status=form.get("employment_status"),
            business_type=form.get("business_type", "").strip() or None,
            created_by_id=current_user.id,
        )
        db.session.add(customer)
        db.session.flush()  # get customer.id for the photo filename

        if photo and photo.filename:
            filename = _save_photo(photo, customer.id)
            if filename and filename != "__invalid__":
                customer.photo_filename = filename

        db.session.commit()
        flash(f"Customer {customer.full_name} was added successfully.", "success")
        return redirect(url_for("customers.view_customer", customer_id=customer.id))

    return render_template("customers/form.html", form={}, id_types=ID_TYPES,
                            employment_statuses=EMPLOYMENT_STATUSES, genders=GENDERS,
                            max_dob=max_allowed_dob().isoformat())


@bp.route("/<int:customer_id>")
@login_required
def view_customer(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    loans = customer.loans.order_by(Loan.created_at.desc()).all()
    return render_template("customers/view.html", customer=customer, loans=loans)


@bp.route("/<int:customer_id>/edit", methods=["GET", "POST"])
@login_required
def edit_customer(customer_id):
    if not current_user.can_edit_customers:
        abort(403)

    customer = Customer.query.get_or_404(customer_id)

    if request.method == "POST":
        form = request.form
        errors = []
        required = ["full_name", "gender", "date_of_birth", "id_type", "id_number",
                    "phone_number", "residential_address", "occupation", "employment_status"]
        for field in required:
            if not form.get(field, "").strip():
                errors.append(f"{field.replace('_', ' ').title()} is required.")

        dob = customer.date_of_birth
        if form.get("date_of_birth"):
            try:
                dob = datetime.strptime(form.get("date_of_birth"), "%Y-%m-%d").date()
            except ValueError:
                errors.append("Date of birth is not valid.")

        min_age = current_app.config["MINIMUM_CUSTOMER_AGE"]
        if dob and dob > max_allowed_dob():
            errors.append(f"Customer must be at least {min_age} years old.")

        photo = request.files.get("photo")
        if photo and photo.filename:
            ext = photo.filename.rsplit(".", 1)[-1].lower() if "." in photo.filename else ""
            if ext not in current_app.config["ALLOWED_IMAGE_EXTENSIONS"]:
                errors.append("Passport picture must be a PNG or JPG image.")

        if errors:
            for e in errors:
                flash(e, "error")
            return render_template("customers/form.html", form=form, customer=customer,
                                    id_types=ID_TYPES, employment_statuses=EMPLOYMENT_STATUSES,
                                    genders=GENDERS, editing=True, max_dob=max_allowed_dob().isoformat())

        customer.full_name = form.get("full_name").strip()
        customer.gender = form.get("gender")
        customer.date_of_birth = dob
        customer.id_type = form.get("id_type")
        customer.id_number = form.get("id_number").strip()
        customer.phone_number = form.get("phone_number").strip()
        customer.residential_address = form.get("residential_address").strip()
        customer.occupation = form.get("occupation").strip()
        customer.employment_status = form.get("employment_status")
        customer.business_type = form.get("business_type", "").strip() or None

        if photo and photo.filename:
            filename = _save_photo(photo, customer.id)
            if filename and filename != "__invalid__":
                _delete_photo(customer.photo_filename)
                customer.photo_filename = filename

        db.session.commit()
        flash("Customer details updated.", "success")
        return redirect(url_for("customers.view_customer", customer_id=customer.id))

    return render_template("customers/form.html", form=customer.__dict__, customer=customer,
                            id_types=ID_TYPES, employment_statuses=EMPLOYMENT_STATUSES,
                            genders=GENDERS, editing=True, max_dob=max_allowed_dob().isoformat())


@bp.route("/<int:customer_id>/statement")
@login_required
def customer_statement(customer_id):
    customer = Customer.query.get_or_404(customer_id)
    loans = customer.loans.order_by(Loan.start_date.asc()).all()

    entries = []
    for loan in loans:
        entries.append({
            "date": loan.start_date,
            "description": f"Loan disbursed — {loan.loan_code} ({loan.term_type} term)",
            "debit": loan.total_repayable,
            "credit": 0,
            "sort_key": (loan.start_date, 0),
        })
        for r in loan.repayments.order_by(Repayment.date.asc()).all():
            entries.append({
                "date": r.date,
                "description": f"Repayment received — {r.transaction_id}" + (f" ({r.note})" if r.note else ""),
                "debit": 0,
                "credit": r.amount,
                "sort_key": (r.date, 1),
            })

    entries.sort(key=lambda e: e["sort_key"])

    running_balance = 0
    for e in entries:
        running_balance += e["debit"] - e["credit"]
        e["balance"] = round(running_balance, 2)

    total_borrowed = sum(l.total_repayable for l in loans)
    total_paid = sum(l.amount_paid for l in loans)

    return render_template(
        "customers/statement.html",
        customer=customer,
        entries=entries,
        total_borrowed=total_borrowed,
        total_paid=total_paid,
        outstanding=round(total_borrowed - total_paid, 2),
        generated_at=datetime.now(),
    )
