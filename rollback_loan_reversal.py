"""
Rollback script to remove loan reversal functionality.
Supports both SQLite and MySQL (pymysql) databases.
WARNING: This will remove all reversal data and cannot be undone!
"""

import sys
import io
# Set UTF-8 encoding for Windows console
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from sqlalchemy import inspect, text
from extensions import db
from app import create_app

def get_database_dialect():
    """Detect the current database dialect."""
    inspector = inspect(db.engine)
    dialect_name = inspector.dialect.name
    print(f"Detected database dialect: {dialect_name}")
    return dialect_name

def column_exists(table_name, column_name):
    """Check if a column exists in a table."""
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def table_exists(table_name):
    """Check if a table exists."""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()

def rollback_sqlite():
    """Run SQLite-specific rollback."""
    print("Running SQLite rollback...")

    # Drop loan reversal logs table
    if table_exists('loan_reversal_logs'):
        print("Dropping loan_reversal_logs table...")
        db.session.execute(text("DROP TABLE loan_reversal_logs"))
        db.session.commit()
        print("[OK] loan_reversal_logs table dropped")
    else:
        print("[OK] loan_reversal_logs table does not exist")

    # Remove reversal tracking from loans table
    if column_exists('loans', 'reversal_reason'):
        print("Removing reversal_reason column from loans table...")
        # SQLite doesn't support DROP COLUMN directly, need to recreate table
        db.session.execute(text("""
            CREATE TABLE loans_new (
                id INTEGER PRIMARY KEY,
                loan_code VARCHAR(20) UNIQUE NOT NULL,
                customer_id INTEGER NOT NULL,
                principal FLOAT NOT NULL,
                interest_rate FLOAT NOT NULL,
                duration_value INTEGER NOT NULL,
                term_type VARCHAR(10) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                total_interest FLOAT NOT NULL,
                total_repayable FLOAT NOT NULL,
                installment_amount FLOAT NOT NULL,
                number_of_installments INTEGER NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                guarantor_customer_id INTEGER,
                guarantor_id INTEGER,
                created_by_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(guarantor_customer_id) REFERENCES customers(id),
                FOREIGN KEY(guarantor_id) REFERENCES guarantors(id),
                FOREIGN KEY(created_by_id) REFERENCES staff(id)
            )
        """))
        db.session.execute(text("""
            INSERT INTO loans_new (
                id, loan_code, customer_id, principal, interest_rate, duration_value,
                term_type, start_date, end_date, total_interest, total_repayable,
                installment_amount, number_of_installments, status, guarantor_customer_id,
                guarantor_id, created_by_id, created_at
            )
            SELECT
                id, loan_code, customer_id, principal, interest_rate, duration_value,
                term_type, start_date, end_date, total_interest, total_repayable,
                installment_amount, number_of_installments, status, guarantor_customer_id,
                guarantor_id, created_by_id, created_at
            FROM loans
        """))
        db.session.execute(text("DROP TABLE loans"))
        db.session.execute(text("ALTER TABLE loans_new RENAME TO loans"))
        db.session.commit()
        print("[OK] reversal_reason column removed")
    else:
        print("[OK] reversal_reason column does not exist")

    if column_exists('loans', 'reversed_by_id'):
        print("Removing reversed_by_id column from loans table...")
        # Similar process for SQLite
        db.session.execute(text("""
            CREATE TABLE loans_new (
                id INTEGER PRIMARY KEY,
                loan_code VARCHAR(20) UNIQUE NOT NULL,
                customer_id INTEGER NOT NULL,
                principal FLOAT NOT NULL,
                interest_rate FLOAT NOT NULL,
                duration_value INTEGER NOT NULL,
                term_type VARCHAR(10) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                total_interest FLOAT NOT NULL,
                total_repayable FLOAT NOT NULL,
                installment_amount FLOAT NOT NULL,
                number_of_installments INTEGER NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                guarantor_customer_id INTEGER,
                guarantor_id INTEGER,
                created_by_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(guarantor_customer_id) REFERENCES customers(id),
                FOREIGN KEY(guarantor_id) REFERENCES guarantors(id),
                FOREIGN KEY(created_by_id) REFERENCES staff(id)
            )
        """))
        db.session.execute(text("""
            INSERT INTO loans_new (
                id, loan_code, customer_id, principal, interest_rate, duration_value,
                term_type, start_date, end_date, total_interest, total_repayable,
                installment_amount, number_of_installments, status, guarantor_customer_id,
                guarantor_id, created_by_id, created_at
            )
            SELECT
                id, loan_code, customer_id, principal, interest_rate, duration_value,
                term_type, start_date, end_date, total_interest, total_repayable,
                installment_amount, number_of_installments, status, guarantor_customer_id,
                guarantor_id, created_by_id, created_at
            FROM loans
        """))
        db.session.execute(text("DROP TABLE loans"))
        db.session.execute(text("ALTER TABLE loans_new RENAME TO loans"))
        db.session.commit()
        print("[OK] reversed_by_id column removed")
    else:
        print("[OK] reversed_by_id column does not exist")

    if column_exists('loans', 'reversed_at'):
        print("Removing reversed_at column from loans table...")
        # Similar process for SQLite
        db.session.execute(text("""
            CREATE TABLE loans_new (
                id INTEGER PRIMARY KEY,
                loan_code VARCHAR(20) UNIQUE NOT NULL,
                customer_id INTEGER NOT NULL,
                principal FLOAT NOT NULL,
                interest_rate FLOAT NOT NULL,
                duration_value INTEGER NOT NULL,
                term_type VARCHAR(10) NOT NULL,
                start_date DATE NOT NULL,
                end_date DATE NOT NULL,
                total_interest FLOAT NOT NULL,
                total_repayable FLOAT NOT NULL,
                installment_amount FLOAT NOT NULL,
                number_of_installments INTEGER NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                guarantor_customer_id INTEGER,
                guarantor_id INTEGER,
                created_by_id INTEGER,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(guarantor_customer_id) REFERENCES customers(id),
                FOREIGN KEY(guarantor_id) REFERENCES guarantors(id),
                FOREIGN KEY(created_by_id) REFERENCES staff(id)
            )
        """))
        db.session.execute(text("""
            INSERT INTO loans_new (
                id, loan_code, customer_id, principal, interest_rate, duration_value,
                term_type, start_date, end_date, total_interest, total_repayable,
                installment_amount, number_of_installments, status, guarantor_customer_id,
                guarantor_id, created_by_id, created_at
            )
            SELECT
                id, loan_code, customer_id, principal, interest_rate, duration_value,
                term_type, start_date, end_date, total_interest, total_repayable,
                installment_amount, number_of_installments, status, guarantor_customer_id,
                guarantor_id, created_by_id, created_at
            FROM loans
        """))
        db.session.execute(text("DROP TABLE loans"))
        db.session.execute(text("ALTER TABLE loans_new RENAME TO loans"))
        db.session.commit()
        print("[OK] reversed_at column removed")
    else:
        print("[OK] reversed_at column does not exist")

    # Remove reverse_loans_permission from staff table
    if column_exists('staff', 'reverse_loans_permission'):
        print("Removing reverse_loans_permission column from staff table...")
        db.session.execute(text("""
            CREATE TABLE staff_new (
                id INTEGER PRIMARY KEY,
                full_name VARCHAR(120) NOT NULL,
                username VARCHAR(64) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                role VARCHAR(20) NOT NULL DEFAULT 'agent',
                is_active_staff BOOLEAN DEFAULT 1 NOT NULL,
                agent_edit_permission BOOLEAN DEFAULT 0 NOT NULL,
                failed_login_attempts INTEGER DEFAULT 0 NOT NULL,
                locked_until DATETIME,
                last_login_at DATETIME,
                must_change_password BOOLEAN DEFAULT 0 NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """))
        db.session.execute(text("""
            INSERT INTO staff_new (
                id, full_name, username, password_hash, role, is_active_staff,
                agent_edit_permission, failed_login_attempts, locked_until,
                last_login_at, must_change_password, created_at
            )
            SELECT
                id, full_name, username, password_hash, role, is_active_staff,
                agent_edit_permission, failed_login_attempts, locked_until,
                last_login_at, must_change_password, created_at
            FROM staff
        """))
        db.session.execute(text("DROP TABLE staff"))
        db.session.execute(text("ALTER TABLE staff_new RENAME TO staff"))
        db.session.commit()
        print("[OK] reverse_loans_permission column removed")
    else:
        print("[OK] reverse_loans_permission column does not exist")

def rollback_mysql():
    """Run MySQL-specific rollback."""
    print("Running MySQL rollback...")

    # Drop loan reversal logs table
    if table_exists('loan_reversal_logs'):
        print("Dropping loan_reversal_logs table...")
        db.session.execute(text("DROP TABLE loan_reversal_logs"))
        db.session.commit()
        print("✓ loan_reversal_logs table dropped")
    else:
        print("✓ loan_reversal_logs table does not exist")

    # Remove reversal tracking from loans table
    if column_exists('loans', 'reversal_reason'):
        print("Removing reversal_reason column from loans table...")
        db.session.execute(text("ALTER TABLE loans DROP COLUMN reversal_reason"))
        db.session.commit()
        print("✓ reversal_reason column removed")
    else:
        print("✓ reversal_reason column does not exist")

    if column_exists('loans', 'reversed_by_id'):
        print("Removing reversed_by_id column from loans table...")
        db.session.execute(text("ALTER TABLE loans DROP COLUMN reversed_by_id"))
        db.session.commit()
        print("✓ reversed_by_id column removed")
    else:
        print("✓ reversed_by_id column does not exist")

    if column_exists('loans', 'reversed_at'):
        print("Removing reversed_at column from loans table...")
        db.session.execute(text("ALTER TABLE loans DROP COLUMN reversed_at"))
        db.session.commit()
        print("✓ reversed_at column removed")
    else:
        print("✓ reversed_at column does not exist")

    # Remove reverse_loans_permission from staff table
    if column_exists('staff', 'reverse_loans_permission'):
        print("Removing reverse_loans_permission column from staff table...")
        db.session.execute(text("ALTER TABLE staff DROP COLUMN reverse_loans_permission"))
        db.session.commit()
        print("✓ reverse_loans_permission column removed")
    else:
        print("✓ reverse_loans_permission column does not exist")

def main():
    """Main rollback function."""
    print("=" * 60)
    print("⚠️  LOAN REVERSAL FEATURE ROLLBACK")
    print("=" * 60)
    print("WARNING: This will remove all reversal data and cannot be undone!")
    print("")

    # Ask for confirmation
    confirm = input("Type 'ROLLBACK' to confirm: ")
    if confirm != "ROLLBACK":
        print("Rollback cancelled.")
        sys.exit(0)

    try:
        # Create app context
        app = create_app()
        with app.app_context():
            # Detect database type
            dialect = get_database_dialect()

            # Run appropriate rollback
            if dialect == 'sqlite':
                rollback_sqlite()
            elif dialect == 'mysql':
                rollback_mysql()
            else:
                print(f"Unsupported database dialect: {dialect}")
                sys.exit(1)

            print("\n" + "=" * 60)
            print("Rollback completed successfully!")
            print("=" * 60)

    except Exception as e:
        print(f"\n❌ Rollback failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()