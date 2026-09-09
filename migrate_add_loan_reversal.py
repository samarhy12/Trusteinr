"""
Migration script to add loan reversal functionality.
Supports both SQLite and MySQL (pymysql) databases.
"""

import sys
import os
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
    """Check if a column already exists in a table."""
    inspector = inspect(db.engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def table_exists(table_name):
    """Check if a table already exists."""
    inspector = inspect(db.engine)
    return table_name in inspector.get_table_names()

def migrate_sqlite():
    """Run SQLite-specific migrations."""
    print("Running SQLite migrations...")

    # Add reverse_loans_permission to staff table
    if not column_exists('staff', 'reverse_loans_permission'):
        print("Adding reverse_loans_permission column to staff table...")
        db.session.execute(text("ALTER TABLE staff ADD COLUMN reverse_loans_permission BOOLEAN DEFAULT 0"))
        db.session.commit()
        print("[OK] reverse_loans_permission column added")
    else:
        print("[OK] reverse_loans_permission column already exists")

    # Add reversal tracking to loans table
    if not column_exists('loans', 'reversed_at'):
        print("Adding reversed_at column to loans table...")
        db.session.execute(text("ALTER TABLE loans ADD COLUMN reversed_at DATETIME"))
        db.session.commit()
        print("[OK] reversed_at column added")
    else:
        print("[OK] reversed_at column already exists")

    if not column_exists('loans', 'reversed_by_id'):
        print("Adding reversed_by_id column to loans table...")
        db.session.execute(text("ALTER TABLE loans ADD COLUMN reversed_by_id INTEGER"))
        db.session.commit()
        print("[OK] reversed_by_id column added")
    else:
        print("[OK] reversed_by_id column already exists")

    if not column_exists('loans', 'reversal_reason'):
        print("Adding reversal_reason column to loans table...")
        db.session.execute(text("ALTER TABLE loans ADD COLUMN reversal_reason TEXT"))
        db.session.commit()
        print("[OK] reversal_reason column added")
    else:
        print("[OK] reversal_reason column already exists")

    # Create loan reversal logs table
    if not table_exists('loan_reversal_logs'):
        print("Creating loan_reversal_logs table...")
        db.session.execute(text("""
            CREATE TABLE loan_reversal_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                loan_id INTEGER NOT NULL,
                loan_code VARCHAR(20) NOT NULL,
                customer_id INTEGER NOT NULL,
                customer_name VARCHAR(120) NOT NULL,
                principal_amount FLOAT NOT NULL,
                reversed_by_id INTEGER NOT NULL,
                reversed_by_name VARCHAR(120) NOT NULL,
                reversed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reason TEXT NOT NULL,
                ip_address VARCHAR(45),
                FOREIGN KEY(loan_id) REFERENCES loans(id),
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(reversed_by_id) REFERENCES staff(id)
            )
        """))
        db.session.commit()
        print("[OK] loan_reversal_logs table created")
    else:
        print("[OK] loan_reversal_logs table already exists")

def migrate_mysql():
    """Run MySQL-specific migrations."""
    print("Running MySQL migrations...")

    # Add reverse_loans_permission to staff table
    if not column_exists('staff', 'reverse_loans_permission'):
        print("Adding reverse_loans_permission column to staff table...")
        db.session.execute(text("ALTER TABLE staff ADD COLUMN reverse_loans_permission BOOLEAN DEFAULT 0"))
        db.session.commit()
        print("[OK] reverse_loans_permission column added")
    else:
        print("[OK] reverse_loans_permission column already exists")

    # Add reversal tracking to loans table
    if not column_exists('loans', 'reversed_at'):
        print("Adding reversed_at column to loans table...")
        db.session.execute(text("ALTER TABLE loans ADD COLUMN reversed_at DATETIME"))
        db.session.commit()
        print("[OK] reversed_at column added")
    else:
        print("[OK] reversed_at column already exists")

    if not column_exists('loans', 'reversed_by_id'):
        print("Adding reversed_by_id column to loans table...")
        db.session.execute(text("ALTER TABLE loans ADD COLUMN reversed_by_id INTEGER"))
        db.session.commit()
        print("[OK] reversed_by_id column added")
    else:
        print("[OK] reversed_by_id column already exists")

    if not column_exists('loans', 'reversal_reason'):
        print("Adding reversal_reason column to loans table...")
        db.session.execute(text("ALTER TABLE loans ADD COLUMN reversal_reason TEXT"))
        db.session.commit()
        print("[OK] reversal_reason column added")
    else:
        print("[OK] reversal_reason column already exists")

    # Create loan reversal logs table
    if not table_exists('loan_reversal_logs'):
        print("Creating loan_reversal_logs table...")
        db.session.execute(text("""
            CREATE TABLE loan_reversal_logs (
                id INT AUTO_INCREMENT PRIMARY KEY,
                loan_id INT NOT NULL,
                loan_code VARCHAR(20) NOT NULL,
                customer_id INT NOT NULL,
                customer_name VARCHAR(120) NOT NULL,
                principal_amount FLOAT NOT NULL,
                reversed_by_id INT NOT NULL,
                reversed_by_name VARCHAR(120) NOT NULL,
                reversed_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                reason TEXT NOT NULL,
                ip_address VARCHAR(45),
                FOREIGN KEY(loan_id) REFERENCES loans(id),
                FOREIGN KEY(customer_id) REFERENCES customers(id),
                FOREIGN KEY(reversed_by_id) REFERENCES staff(id)
            )
        """))
        db.session.commit()
        print("[OK] loan_reversal_logs table created")
    else:
        print("[OK] loan_reversal_logs table already exists")

def enable_admin_permissions():
    """Enable reversal permission for existing admins."""
    print("Enabling reversal permission for existing admins...")
    result = db.session.execute(text(
        "UPDATE staff SET reverse_loans_permission = 1 WHERE role = 'admin'"
    ))
    db.session.commit()
    updated_count = result.rowcount
    print(f"[OK] Enabled reversal permission for {updated_count} admin(s)")

def verify_migration():
    """Verify that the migration was successful."""
    print("\nVerifying migration...")

    # Check staff table
    staff_columns = [col['name'] for col in inspect(db.engine).get_columns('staff')]
    print(f"Staff table columns: {staff_columns}")
    assert 'reverse_loans_permission' in staff_columns, "reverse_loans_permission column missing in staff table"

    # Check loans table
    loans_columns = [col['name'] for col in inspect(db.engine).get_columns('loans')]
    print(f"Loans table columns: {loans_columns}")
    assert 'reversed_at' in loans_columns, "reversed_at column missing in loans table"
    assert 'reversed_by_id' in loans_columns, "reversed_by_id column missing in loans table"
    assert 'reversal_reason' in loans_columns, "reversal_reason column missing in loans table"

    # Check loan_reversal_logs table
    assert table_exists('loan_reversal_logs'), "loan_reversal_logs table missing"

    print("[OK] Migration verification successful!")

def main():
    """Main migration function."""
    print("=" * 60)
    print("Loan Reversal Feature Migration")
    print("=" * 60)

    try:
        # Create app context
        app = create_app()
        with app.app_context():
            # Detect database type
            dialect = get_database_dialect()

            # Run appropriate migration
            if dialect == 'sqlite':
                migrate_sqlite()
            elif dialect == 'mysql':
                migrate_mysql()
            else:
                print(f"Unsupported database dialect: {dialect}")
                sys.exit(1)

            # Enable admin permissions
            enable_admin_permissions()

            # Verify migration
            verify_migration()

            print("\n" + "=" * 60)
            print("Migration completed successfully!")
            print("=" * 60)

    except Exception as e:
        print(f"\n[ERROR] Migration failed: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()