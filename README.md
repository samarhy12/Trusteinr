# Trustline Finance — Staff Portal

A multi-staff loan management system for Trustline Finance: customer records, loan disbursement with automatic interest and schedule calculation, daily/weekly/monthly repayment tracking, and a live cash-in-hand ledger. Built as a Progressive Web App (installable on phones and desktops) with Flask + SQLAlchemy on the backend, and Tailwind CSS + Alpine.js on the frontend — fully responsive from phone to desktop.

## Staff roles

There are three account types (set when creating a staff account under *Staff Accounts*, admin only):

| | Admin | Office Staff | Agent |
|---|---|---|---|
| View dashboard, customers, loans, transactions, expenses, agent reports, statements | ✅ | ✅ | ✅ |
| Register customers | ✅ | ✅ | ✅ |
| Edit customer details | ✅ | ❌ | Only if admin grants it for that agent (toggle on the Staff Accounts page) |
| Disburse loans | ✅ | ❌ | ❌ |
| Record repayments | ✅ | ✅ | ❌ |
| Record expenses | ✅ | ❌ | ❌ |
| Adjust the cash ledger, manage staff, open/close the business day | ✅ | ❌ | ❌ |

## Business rules implemented

- **Login** — every action requires a staff username/password (Phase 1).
- **Customer records** — name, gender, date of birth, ID type/number, phone, address, occupation, employment status, business type, and an optional passport picture upload (Phase 2). Customers must be at least 18 years old — the date picker and the server both enforce this.
- **Loan interest** — 10% per month by default, but staff can enter a custom rate per loan. Total repayable = principal + (principal × monthly rate × duration in months).
- **Repayment terms & duration** — daily (Monday–Friday only, weekends excluded), weekly, or monthly, each with its own custom duration entered per loan: number of days for daily, number of weeks for weekly, number of months for monthly (Phase 3). Weekly/daily durations convert to a month-equivalent for interest using the standard 4-weeks/30-days-per-month approximation.
- **Transaction IDs** — every repayment gets a human-readable transaction ID: the payment date plus the customer's sequential registration number (the 1st customer ever registered is #1, the 2nd is #2, and so on), e.g. `2026070724` for a payment on 7 July 2026 from customer #24. If the same customer pays twice in one day, a `-2`, `-3`, ... suffix keeps IDs unique. Every transaction ID doubles as the receipt number and can be looked up anytime under *Find Transaction*.
- **Repayments** — every repayment records which agent physically collected the cash (separate from who typed it in), the date, amount, and a receipt code. Amount paid and outstanding balance are always shown live (Phase 4).
- **Guarantors** — every loan requires a guarantor, either picked from existing customers or entered fresh with the same details (and 18+ rule) as a customer, including a passport photo.
- **Agent reports** — click any agent to see their collections for a chosen day (defaults to today) or all-time, with customer name, account number, contact, loan, and amount — printable.
- **Business day control** — an admin opens the day each morning; while open, office staff and agents can work normally. Closing the day (with a confirmation step) locks in that day's totals permanently and blocks *everyone*, including admin, from recording new loans/repayments/expenses until it's reopened. Office staff and agents are fully locked out of the whole system while the day is closed or unopened, and automatically every Saturday and Sunday. Every past day's report stays accessible under Business Day → history.
- **Customer statements** — a printable, all-time statement of every loan and repayment for a customer with a running balance, accessible from their profile.
- **Daily expenses** — admins log operating costs (rent, transport, airtime, salaries, etc.); each entry is deducted from cash in hand automatically.
- **Cash ledger control** — manual cash adjustments (capital injections/withdrawals) are restricted to admins and require the admin's password to confirm, in addition to the normal login.

## Uploaded files

Passport pictures are stored on disk under `static/uploads/customers/`. If you deploy to a host with an ephemeral filesystem (e.g. some free-tier PaaS), point `UPLOAD_FOLDER` in `config.py` at a persistent volume or object storage, or these images will be lost on redeploy.

## Getting started

```bash
cd cashpoint
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python3 app.py
```

Open **http://localhost:5000** in your browser.

The compiled stylesheet (`static/css/tailwind.css`) is already built and committed, so the app works immediately with just the Python steps above — you do **not** need Node.js to run it.

### Changing styles (optional)

If you want to change colors, spacing, or add new utility classes, edit `static/css/input.css` or `tailwind.config.js`, then rebuild:

```bash
npm install
npm run build:css     # one-off build
npm run watch:css      # rebuilds automatically as you edit
```

On first run, the app creates a database at `instance/cashpoint.db` and a default administrator account:

- **Username:** `admin`
- **Password:** `admin123`

You'll be **required to set your own password immediately** on first login — this is enforced by the system, not just a suggestion.

## Security

This app is built with several production-grade protections already in place:

- **CSRF protection** on every form (a hidden token tied to your session; requests without a valid one are rejected).
- **Account lockout** — 5 failed login attempts locks an account for 15 minutes (configurable in `config.py`).
- **Forced password change** — new accounts and password resets require the person to set their own password before doing anything else.
- **Admin-initiated password resets** — if someone forgets their password, an admin can reset it from *Staff Accounts* without needing database access; a one-time temporary password is shown once and must be shared securely.
- **Secure image uploads** — passport pictures are verified as genuine images (not just checked by file extension) and re-encoded before saving, which strips hidden metadata and neutralizes disguised malicious files.
- **Hardened sessions** — HTTP-only, `SameSite=Lax` cookies; sessions expire after 12 hours by default, or 14 days if "Keep me signed in" is checked at login.
- **Security headers** — `X-Frame-Options`, `X-Content-Type-Options`, and `Referrer-Policy` are set on every response.
- **Role-based access control** — enforced at the route level for every action (see the roles table above), not just hidden in the UI.

For production, also do the following (see *Deploying for real use* below): set a real `SECRET_KEY`, serve over HTTPS and set `FORCE_HTTPS=1`, and keep regular database backups since this holds real financial records.

## Loading sample data for testing

To try out every feature without typing data by hand, run:

```bash
python3 seed.py
```

This **wipes the database** and rebuilds it with realistic sample data: 6 staff accounts (1 admin, 2 office staff, 3 agents), 10 customers, a mix of loans in every status (active, overdue, completed), repayments spread across the last few weeks and tagged to different agents, expenses, and two weeks of business day history (with today opened and ready to use). It prints all the login credentials when done — only run it against a development database, never in production.

## Installing as an app (PWA)

Once the site is open in Chrome/Edge on desktop or Android, use the browser's "Install app" option (or "Add to Home Screen" on iOS Safari) to install Trustline Finance like a native app. It will work fully offline for the app shell; live data still needs a network connection to your server.

## Deploying for real use

The built-in `python3 app.py` server is for development only. For staff to use this day-to-day (especially from phones outside your office), deploy it properly:

1. Put the project on a small server or a host like Render, PythonAnywhere, or a VPS.
2. Run it with a production server, e.g.:
   ```bash
   pip install gunicorn
   gunicorn -w 4 -b 0.0.0.0:8000 app:app
   ```
3. Put it behind HTTPS (e.g. via Nginx + Let's Encrypt, or your host's built-in HTTPS) — this is essential since staff will be typing passwords and handling customer financial data. Once HTTPS is in place, set the environment variable `FORCE_HTTPS=1` so session cookies are marked secure.
4. Set a strong `SECRET_KEY` environment variable in production instead of the default in `config.py`.
5. Consider switching `DATABASE_URL` to PostgreSQL/MySQL if you expect many staff working at once — SQLite (the default) is fine for a single school/branch getting started.
6. Back up `instance/cashpoint.db` (or your production database) regularly — this holds real loan, repayment and customer records.

## Project structure

```
cashpoint/
├── app.py                    # App factory, security headers, access control
├── config.py                  # Business rules + security settings
├── models.py                   # Staff, Customer, Loan, Repayment, CashTransaction, etc.
├── extensions.py                # SQLAlchemy + Flask-Login setup
├── security.py                   # CSRF protection
├── image_utils.py                 # Secure image upload validation
├── seed.py                          # Sample data generator (see below)
├── routes/                           # auth, dashboard, customers, loans, staff, expenses, agents, business blueprints
├── templates/                         # Jinja2 templates (Tailwind CSS, navy/gold theme)
├── tailwind.config.js                  # Brand colors & fonts for Tailwind
├── package.json                         # npm scripts to rebuild CSS (optional, not needed to run the app)
└── static/
    ├── css/input.css                        # Tailwind source (edit this to restyle)
    ├── css/tailwind.css                      # Compiled, minified CSS actually served to the browser
    ├── js/app.js                              # Service worker registration, loan preview, double-submit guard
    └── manifest.json, service-worker.js, icons/   # PWA assets
```

## Changing the business rules

`config.py` holds the default interest rate, offered as the "standard" preset on the loan form (staff can always override it with a custom rate per loan):

```python
MONTHLY_INTEREST_RATE = 0.10   # 10% per month — shown as the default option, not enforced
```

Loan duration is no longer fixed — it's entered per loan (days for daily terms, weeks for weekly, months for monthly). The schedule math itself lives in `Loan.compute_schedule` in `models.py` if you ever need to change how weekly/daily durations convert to month-equivalents for interest (currently 4 weeks ≈ 1 month, 30 days ≈ 1 month).
#   C a s h p o i n t  
 #   C a s h p o i n t  
 #   C a s h p o i n t  
 #   T r u s t e i n r  
 