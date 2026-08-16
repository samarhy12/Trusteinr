import enum
from datetime import date, timedelta, datetime
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

from extensions import db


def gen_ref(prefix):
    """Generate a short human-readable reference code."""
    import random
    import string
    suffix = "".join(random.choices(string.digits, k=6))
    return f"{prefix}-{suffix}"


# ---------------------------------------------------------------------------
# Staff / Auth
# ---------------------------------------------------------------------------
class Staff(UserMixin, db.Model):
    __tablename__ = "staff"

    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="agent")  # admin | office_staff | agent
    is_active_staff = db.Column(db.Boolean, default=True, nullable=False)

    # Admin-controlled: allows a specific agent to edit customer records they wouldn't otherwise touch.
    agent_edit_permission = db.Column(db.Boolean, default=False, nullable=False)

    # Login security
    failed_login_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    must_change_password = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=db.func.now())

    loans_created = db.relationship("Loan", backref="created_by", lazy="dynamic",
                                     foreign_keys="Loan.created_by_id")
    customers_created = db.relationship("Customer", backref="created_by", lazy="dynamic",
                                         foreign_keys="Customer.created_by_id")

    def set_password(self, raw_password):
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password):
        return check_password_hash(self.password_hash, raw_password)

    @property
    def is_locked(self):
        from datetime import datetime
        return bool(self.locked_until and self.locked_until > datetime.now())

    def register_failed_login(self, max_attempts, lockout_minutes):
        from datetime import datetime, timedelta as _td
        self.failed_login_attempts = (self.failed_login_attempts or 0) + 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = datetime.now() + _td(minutes=lockout_minutes)
            self.failed_login_attempts = 0

    def register_successful_login(self):
        from datetime import datetime
        self.failed_login_attempts = 0
        self.locked_until = None
        self.last_login_at = datetime.now()

    @property
    def is_admin(self):
        return self.role == "admin"

    @property
    def is_office_staff(self):
        return self.role == "office_staff"

    @property
    def is_agent(self):
        return self.role == "agent"

    @property
    def role_label(self):
        return {"admin": "Admin", "office_staff": "Office Staff", "agent": "Agent"}.get(self.role, self.role)

    # ---- permission helpers used throughout routes/templates ----
    @property
    def can_register_customers(self):
        return self.role in ("admin", "office_staff", "agent")

    @property
    def can_edit_customers(self):
        return self.role == "admin" or (self.role == "agent" and self.agent_edit_permission)

    @property
    def can_disburse_loans(self):
        return self.role == "admin"

    @property
    def can_record_repayments(self):
        return self.role in ("admin", "office_staff")

    @property
    def can_record_expenses(self):
        return self.role == "admin"

    @property
    def can_manage_cash_ledger(self):
        return self.role == "admin"

    @property
    def can_manage_staff(self):
        return self.role == "admin"

    @property
    def can_manage_business_day(self):
        return self.role == "admin"

    # flask-login requires an active account to allow login
    @property
    def is_active(self):
        return self.is_active_staff

    def __repr__(self):
        return f"<Staff {self.username}>"


# ---------------------------------------------------------------------------
# Customer
# ---------------------------------------------------------------------------
class Customer(db.Model):
    __tablename__ = "customers"

    id = db.Column(db.Integer, primary_key=True)
    customer_code = db.Column(db.String(20), unique=True, nullable=False, default=lambda: gen_ref("CP"))

    # Sequential number based purely on registration order — 1 for the very first
    # customer ever registered, 2 for the next, and so on. Used to build transaction IDs.
    registration_number = db.Column(db.Integer, unique=True, nullable=False)

    full_name = db.Column(db.String(150), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)

    id_type = db.Column(db.String(50), nullable=False)
    id_number = db.Column(db.String(80), nullable=False)

    phone_number = db.Column(db.String(20), nullable=False)
    residential_address = db.Column(db.String(255), nullable=False)

    occupation = db.Column(db.String(100), nullable=False)
    employment_status = db.Column(db.String(50), nullable=False)
    business_type = db.Column(db.String(120), nullable=True)

    photo_filename = db.Column(db.String(255), nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    loans = db.relationship("Loan", backref="customer", lazy="dynamic", cascade="all, delete-orphan",
                             foreign_keys="Loan.customer_id")

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    @property
    def active_loans(self):
        return self.loans.filter(Loan.status == "active").all()

    @property
    def total_borrowed(self):
        return sum(l.principal for l in self.loans)

    def __repr__(self):
        return f"<Customer {self.full_name}>"


def next_registration_number():
    """The next sequential customer registration number (1 for the very first customer)."""
    highest = db.session.query(db.func.coalesce(db.func.max(Customer.registration_number), 0)).scalar()
    return (highest or 0) + 1


# ---------------------------------------------------------------------------
# Guarantor (freshly-entered person, as opposed to an existing customer
# selected as a guarantor — see Loan.guarantor_customer_id / guarantor_id)
# ---------------------------------------------------------------------------
class Guarantor(db.Model):
    __tablename__ = "guarantors"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(150), nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    date_of_birth = db.Column(db.Date, nullable=False)

    id_type = db.Column(db.String(50), nullable=False)
    id_number = db.Column(db.String(80), nullable=False)

    phone_number = db.Column(db.String(20), nullable=False)
    residential_address = db.Column(db.String(255), nullable=False)

    occupation = db.Column(db.String(100), nullable=False)
    employment_status = db.Column(db.String(50), nullable=False)
    business_type = db.Column(db.String(120), nullable=True)
    relationship_to_customer = db.Column(db.String(50), nullable=True)

    photo_filename = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    @property
    def age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - (
            (today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day)
        )

    def __repr__(self):
        return f"<Guarantor {self.full_name}>"


# ---------------------------------------------------------------------------
# Loan
# ---------------------------------------------------------------------------
class TermType(str, enum.Enum):
    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"


class Loan(db.Model):
    __tablename__ = "loans"

    id = db.Column(db.Integer, primary_key=True)
    loan_code = db.Column(db.String(20), unique=True, nullable=False, default=lambda: gen_ref("LN"))

    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=False)

    principal = db.Column(db.Float, nullable=False)
    interest_rate = db.Column(db.Float, nullable=False)      # rate per month, e.g. 0.10 for 10% — may be custom
    duration_value = db.Column(db.Integer, nullable=False)    # count in the unit implied by term_type
    term_type = db.Column(db.String(10), nullable=False)     # daily | weekly | monthly — also sets the duration unit

    start_date = db.Column(db.Date, nullable=False)
    end_date = db.Column(db.Date, nullable=False)

    total_interest = db.Column(db.Float, nullable=False)
    total_repayable = db.Column(db.Float, nullable=False)
    installment_amount = db.Column(db.Float, nullable=False)
    number_of_installments = db.Column(db.Integer, nullable=False)

    status = db.Column(db.String(20), nullable=False, default="active")  # active | completed | defaulted

    # Guarantor is EITHER an existing customer OR a freshly-entered person — exactly one should be set.
    guarantor_customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    guarantor_id = db.Column(db.Integer, db.ForeignKey("guarantors.id"), nullable=True)

    created_by_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    guarantor_customer = db.relationship("Customer", foreign_keys=[guarantor_customer_id])
    guarantor = db.relationship("Guarantor", foreign_keys=[guarantor_id])

    repayments = db.relationship("Repayment", backref="loan", lazy="dynamic",
                                  cascade="all, delete-orphan", order_by="Repayment.date")

    @property
    def guarantor_name(self):
        if self.guarantor_customer:
            return self.guarantor_customer.full_name
        if self.guarantor:
            return self.guarantor.full_name
        return None

    @property
    def guarantor_phone(self):
        if self.guarantor_customer:
            return self.guarantor_customer.phone_number
        if self.guarantor:
            return self.guarantor.phone_number
        return None

    # ---- computed helpers ----
    @property
    def amount_paid(self):
        total = db.session.query(db.func.coalesce(db.func.sum(Repayment.amount), 0.0)) \
            .filter(Repayment.loan_id == self.id).scalar()
        return float(total or 0.0)

    @property
    def outstanding_balance(self):
        return round(self.total_repayable - self.amount_paid, 2)

    @property
    def is_overdue(self):
        return self.status == "active" and date.today() > self.end_date and self.outstanding_balance > 0

    @property
    def progress_percent(self):
        if self.total_repayable <= 0:
            return 100
        pct = (self.amount_paid / self.total_repayable) * 100
        return max(0, min(100, round(pct, 1)))

    def get_next_due_date(self):
        """Calculate the next installment due date based on term type and payment history."""
        if self.status != "active":
            return None
        
        # Get the most recent payment date, or use start date if no payments
        # Use SQL to avoid circular dependency with Repayment model
        try:
            last_payment = db.session.execute(
                db.text("SELECT date FROM repayments WHERE loan_id = :loan_id ORDER BY date DESC LIMIT 1"),
                {"loan_id": self.id}
            ).fetchone()
            has_last_payment = last_payment is not None
            # Convert string to date object if needed
            if last_payment and last_payment[0]:
                if isinstance(last_payment[0], str):
                    last_payment_date = datetime.strptime(last_payment[0], "%Y-%m-%d").date()
                else:
                    last_payment_date = last_payment[0]
            else:
                last_payment_date = None
        except:
            has_last_payment = False
            last_payment_date = None
        
        # Calculate the next due date based on term type
        if self.term_type == TermType.MONTHLY.value:
            # First payment due 1 month after disbursement, then monthly thereafter
            if has_last_payment and last_payment_date:
                return add_months(last_payment_date, 1)
            else:
                return add_months(self.start_date, 1)
        elif self.term_type == TermType.WEEKLY.value:
            # First payment due 1 week after disbursement, then weekly thereafter
            base_date = last_payment_date if (has_last_payment and last_payment_date) else self.start_date
            return base_date + timedelta(weeks=1)
        else:  # daily
            # First payment due 1 week after disbursement, then business days thereafter
            if has_last_payment and last_payment_date:
                return add_weekdays(last_payment_date, 1)
            else:
                return self.start_date + timedelta(weeks=1)

    @property
    def next_due_date(self):
        """Get the next installment due date."""
        return self.get_next_due_date()

    @property
    def days_until_due(self):
        """Days until next payment is due (negative if overdue)."""
        next_due = self.next_due_date
        if not next_due:
            return None
        return (next_due - date.today()).days

    @property
    def is_payment_due_today(self):
        """Check if a payment is due today."""
        next_due = self.next_due_date
        return next_due == date.today() if next_due else False

    @property
    def is_payment_overdue(self):
        """Check if a payment is overdue (past due date and still active)."""
        if self.status != "active":
            return False
        days_until = self.days_until_due
        return days_until is not None and days_until < 0

    @property
    def overdue_days(self):
        """Number of days the payment is overdue."""
        days_until = self.days_until_due
        return abs(days_until) if days_until is not None and days_until < 0 else 0

    def refresh_status(self):
        if self.outstanding_balance <= 0:
            self.status = "completed"
        elif self.is_overdue:
            self.status = "defaulted" if False else "active"  # kept active but flagged overdue via is_overdue
        else:
            if self.status == "completed":
                self.status = "active"

    @staticmethod
    def compute_schedule(principal, monthly_rate, term_type, duration_value, start_date):
        """
        Return (end_date, total_interest, total_repayable, installment_amount, num_installments).

        duration_value is a count in whatever unit term_type implies:
          - monthly: number of months (e.g. 4)
          - weekly:  number of weeks (e.g. 6)
          - daily:   number of weekdays (Mon-Fri) in the loan term. Weekends are
                     skipped, so the installment count is based on business days.

        Interest is charged per month at monthly_rate. Weekly durations are converted
        to a month-equivalent using the standard microfinance approximation of 4 weeks
        per month. Daily durations accrue interest on weekdays only, so the month-
        equivalent is the business-day count divided by 20 (5 weekdays/week x 4 weeks/month).
        
        Payment schedule:
        - Monthly loans: First payment 1 month after disbursement, then monthly
        - Weekly loans: First payment 1 week after disbursement, then weekly
        - Daily loans: First payment 1 week after disbursement, then business days
        """
        duration_value = max(1, int(duration_value))

        if term_type == TermType.MONTHLY.value:
            # First payment 1 month after disbursement, then monthly
            end_date = add_months(start_date, duration_value)
            effective_months = duration_value
            num_installments = duration_value
        elif term_type == TermType.WEEKLY.value:
            end_date = start_date + timedelta(weeks=duration_value)
            effective_months = duration_value / 4.0
            num_installments = duration_value
        else:  # daily -> weekdays only (Mon-Fri), weekends excluded
            # Start payments 1 week after disbursement, then count business days
            first_payment_date = start_date + timedelta(weeks=1)
            end_date = add_weekdays(first_payment_date, duration_value - 1)
            num_installments = max(1, duration_value)
            effective_months = num_installments / 20.0

        total_interest = round(principal * monthly_rate * effective_months, 2)
        total_repayable = round(principal + total_interest, 2)
        installment = round(total_repayable / num_installments, 2)
        return end_date, total_interest, total_repayable, installment, num_installments

    def __repr__(self):
        return f"<Loan {self.loan_code}>"


def subtract_years(d, years):
    """Return the date `years` before d, handling Feb 29 safely."""
    try:
        return d.replace(year=d.year - years)
    except ValueError:
        return d.replace(year=d.year - years, day=28)


def add_months(d, months):
    month = d.month - 1 + months
    year = d.year + month // 12
    month = month % 12 + 1
    day = min(d.day, [31, 29 if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0) else 28,
                       31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month - 1])
    return date(year, month, day)


def add_weekdays(start_date, weekdays):
    """Return the date after a given number of weekdays, skipping weekends."""
    if weekdays <= 0:
        return start_date

    current = start_date
    remaining = weekdays
    while remaining > 0:
        if current.weekday() < 5:  # 0=Mon .. 4=Fri
            remaining -= 1
            if remaining == 0:
                return current
        current += timedelta(days=1)
    return current


# ---------------------------------------------------------------------------
# Repayment
# ---------------------------------------------------------------------------
def generate_transaction_id(customer, tx_date):
    """
    Build a human-readable transaction ID: the payment date plus the customer's
    sequential registration number, e.g. 2026070724 for a payment on 7 July 2026
    from the 24th customer ever registered. If that exact ID is already taken
    (a second payment from the same customer on the same day), a "-2", "-3", ...
    suffix is appended to keep every ID unique.
    """
    base = f"{tx_date.strftime('%Y%m%d')}{customer.registration_number}"
    candidate = base
    suffix = 1
    while Repayment.query.filter_by(transaction_id=candidate).first() is not None:
        suffix += 1
        candidate = f"{base}-{suffix}"
    return candidate


class Repayment(db.Model):
    __tablename__ = "repayments"

    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.String(30), unique=True, nullable=False)

    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id"), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)
    note = db.Column(db.String(255), nullable=True)

    # The agent who physically collected the cash in the field (may differ from who typed it in).
    agent_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=False)
    recorded_by_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    agent = db.relationship("Staff", foreign_keys=[agent_id])
    recorded_by = db.relationship("Staff", foreign_keys=[recorded_by_id])

    def __repr__(self):
        return f"<Repayment {self.transaction_id}>"


# ---------------------------------------------------------------------------
# Cash transaction ledger (cash-in-hand tracking)
# ---------------------------------------------------------------------------
class CashTransaction(db.Model):
    __tablename__ = "cash_transactions"

    id = db.Column(db.Integer, primary_key=True)
    tx_type = db.Column(db.String(30), nullable=False)  # capital_in | disbursement | repayment | expense | adjustment
    amount = db.Column(db.Float, nullable=False)         # signed: +in, -out
    description = db.Column(db.String(255), nullable=True)

    loan_id = db.Column(db.Integer, db.ForeignKey("loans.id"), nullable=True)
    customer_id = db.Column(db.Integer, db.ForeignKey("customers.id"), nullable=True)
    expense_id = db.Column(db.Integer, db.ForeignKey("expenses.id"), nullable=True)
    staff_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)

    date = db.Column(db.Date, nullable=False, default=date.today)
    created_at = db.Column(db.DateTime, default=db.func.now())

    loan = db.relationship("Loan")
    customer = db.relationship("Customer")
    staff = db.relationship("Staff")

    def __repr__(self):
        return f"<CashTx {self.tx_type} {self.amount}>"


# ---------------------------------------------------------------------------
# Daily expenses
# ---------------------------------------------------------------------------
EXPENSE_CATEGORIES = [
    "Rent", "Transport", "Airtime & Data", "Utilities", "Salaries",
    "Office Supplies", "Stationery", "Maintenance", "Miscellaneous",
]


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    expense_code = db.Column(db.String(20), unique=True, nullable=False, default=lambda: gen_ref("EX"))

    description = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False, default=date.today)

    recorded_by_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=db.func.now())

    recorded_by = db.relationship("Staff", foreign_keys=[recorded_by_id])

    def __repr__(self):
        return f"<Expense {self.expense_code}>"


def current_cash_in_hand():
    total = db.session.query(db.func.coalesce(db.func.sum(CashTransaction.amount), 0.0)).scalar()
    return round(float(total or 0.0), 2)


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------
class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.String(50), nullable=False, default="due_loans")  # due_loans, overdue, system
    recipient_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)
    recipient_role = db.Column(db.String(50), nullable=True)  # admin, office_staff, agent, or specific user
    
    is_read = db.Column(db.Boolean, default=False, nullable=False)
    created_at = db.Column(db.DateTime, default=db.func.now())
    read_at = db.Column(db.DateTime, nullable=True)

    # For due loans notifications, store the relevant data
    loan_data = db.Column(db.JSON, nullable=True)  # Store loan IDs, counts, etc.

    recipient = db.relationship("Staff", foreign_keys=[recipient_id])

    def __repr__(self):
        return f"<Notification {self.title}>"


# ---------------------------------------------------------------------------
# Business day open/close control
# ---------------------------------------------------------------------------
class BusinessDay(db.Model):
    __tablename__ = "business_days"

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False)

    opened_at = db.Column(db.DateTime, nullable=True)
    opened_by_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)

    closed_at = db.Column(db.DateTime, nullable=True)
    closed_by_id = db.Column(db.Integer, db.ForeignKey("staff.id"), nullable=True)

    # Snapshot totals captured at close time, for a fast historical list.
    total_collected = db.Column(db.Float, nullable=True)
    total_disbursed = db.Column(db.Float, nullable=True)
    total_expenses = db.Column(db.Float, nullable=True)
    net_change = db.Column(db.Float, nullable=True)

    opened_by = db.relationship("Staff", foreign_keys=[opened_by_id])
    closed_by = db.relationship("Staff", foreign_keys=[closed_by_id])

    @property
    def is_open(self):
        return self.opened_at is not None and self.closed_at is None

    def __repr__(self):
        return f"<BusinessDay {self.date} open={self.is_open}>"


def is_weekend(d=None):
    d = d or date.today()
    return d.weekday() >= 5  # 5=Saturday, 6=Sunday


def get_business_day(d=None, create_if_missing=False):
    d = d or date.today()
    row = BusinessDay.query.filter_by(date=d).first()
    if row is None and create_if_missing:
        row = BusinessDay(date=d)
        db.session.add(row)
        db.session.flush()
    return row


def is_business_day_open(d=None):
    """True only if today has an explicit open BusinessDay row (weekends are never auto-open)."""
    d = d or date.today()
    row = BusinessDay.query.filter_by(date=d).first()
    return bool(row and row.is_open)
