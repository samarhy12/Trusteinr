"""
Migration script to add cash transaction reversal functionality.
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

def migrate_sqlite():
    """Run SQLite-specific migrations."""
    print("Running SQLite migrations...")

    # Add reversal tracking to cash_transactions table
    if not column_exists('cash_transactions', 'reversed_by_id'):
        print("Adding reversed_by_id column to cash_transactions table...")
        db.session.execute(text("ALTER TABLE cash_transactions ADD COLUMN reversed_by_id INTEGER"))
        db.session.commit()
        print("[OK] reversed_by_id column added")
    else:
        print("[OK] reversed_by_id column already exists")

    if not column_exists('cash_transactions', 'reversed_at'):
        print("Adding reversed_at column to cash_transactions table...")
        db.session.execute(text("ALTER TABLE cash_transactions ADD COLUMN reversed_at DATETIME"))
        db.session.commit()
        print("[OK] reversed_at column added")
    else:
        print("[OK] reversed_at column already exists")

    if not column_exists('cash_transactions', 'reversal_reason'):
        print("Adding reversal_reason column to cash_transactions table...")
        db.session.execute(text("ALTER TABLE cash_transactions ADD COLUMN reversal_reason VARCHAR(255)"))
        db.session.commit()
        print("[OK] reversal_reason column added")
    else:
        print("[OK] reversal_reason column already exists")

    if not column_exists('cash_transactions', 'original_tx_id'):
        print("Adding original_tx_id column to cash_transactions table...")
        db.session.execute(text("ALTER TABLE cash_transactions ADD COLUMN original_tx_id INTEGER"))
        db.session.commit()
        print("[OK] original_tx_id column added")
    else:
        print("[OK] original_tx_id column already exists")

def migrate_mysql():
    """Run MySQL-specific migrations."""
    print("Running MySQL migrations...")

    # Add reversal tracking to cash_transactions table
    if not column_exists('cash_transactions', 'reversed_by_id'):
        print("Adding reversed_by_id column to cash_transactions table...")
        db.session.execute(text("ALTER TABLE cash_transactions ADD COLUMN reversed_by_id INTEGER"))
        db.session.commit()
        print("[OK] reversed_by_id column added")
    else:
        print("[OK] reversed_by_id column already exists")

    if not column_exists('cash_transactions', 'reversed_at'):
        print("Adding reversed_at column to cash_transactions table...")
        db.session.execute(text("ALTER TABLE cash_transactions ADD COLUMN reversed_at DATETIME"))
        db.session.commit()
        print("[OK] reversed_at column added")
    else:
        print("[OK] reversed_at column already exists")

    if not column_exists('cash_transactions', 'reversal_reason'):
        print("Adding reversal_reason column to cash_transactions table...")
        db.session.execute(text("ALTER TABLE cash_transactions ADD COLUMN reversal_reason VARCHAR(255)"))
        db.session.commit()
        print("[OK] reversal_reason column added")
    else:
        print("[OK] reversal_reason column already exists")

    if not column_exists('cash_transactions', 'original_tx_id'):
        print("Adding original_tx_id column to cash_transactions table...")
        db.session.execute(text("ALTER TABLE cash_transactions ADD COLUMN original_tx_id INTEGER"))
        db.session.commit()
        print("[OK] original_tx_id column added")
    else:
        print("[OK] original_tx_id column already exists")

def verify_migration():
    """Verify that the migration was successful."""
    print("\nVerifying migration...")

    # Check cash_transactions table
    cash_tx_columns = [col['name'] for col in inspect(db.engine).get_columns('cash_transactions')]
    print(f"Cash transactions table columns: {cash_tx_columns}")
    assert 'reversed_by_id' in cash_tx_columns, "reversed_by_id column missing in cash_transactions table"
    assert 'reversed_at' in cash_tx_columns, "reversed_at column missing in cash_transactions table"
    assert 'reversal_reason' in cash_tx_columns, "reversal_reason column missing in cash_transactions table"
    assert 'original_tx_id' in cash_tx_columns, "original_tx_id column missing in cash_transactions table"

    print("[OK] Migration verification successful!")

def main():
    """Main migration function."""
    print("=" * 60)
    print("Cash Transaction Reversal Feature Migration")
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