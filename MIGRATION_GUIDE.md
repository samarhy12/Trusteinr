# Loan Reversal Feature Migration Guide

This guide explains how to migrate your database to support the new loan reversal functionality.

## Features Being Added

- **Loan Reversal**: Admins can reverse mistakenly disbursed loans
- **Audit Logging**: Complete audit trail of all reversals
- **Permission Control**: Separate permission for loan reversal (admin-only)
- **Multi-layer Safeguards**: Password re-authentication, detailed reasons, confirmation

## Database Changes

### New Columns
- `staff.reverse_loans_permission` (BOOLEAN, default: 0)
- `loans.reversed_at` (DATETIME, nullable)
- `loans.reversed_by_id` (INTEGER, nullable)
- `loans.reversal_reason` (TEXT, nullable)

### New Table
- `loan_reversal_logs` (complete audit trail of reversals)

## Migration Steps

### 1. Backup Your Database

**SQLite:**
```bash
cp instance/cashpoint.db instance/cashpoint.db.backup
```

**MySQL:**
```bash
mysqldump -u username -p database_name > backup.sql
```

### 2. Run Migration Script

The migration script automatically detects your database type (SQLite or MySQL) and runs the appropriate migrations.

```bash
python migrate_add_loan_reversal.py
```

### 3. What the Script Does

1. **Detects database type** (SQLite or MySQL)
2. **Adds new columns** to existing tables
3. **Creates audit log table**
4. **Enables reversal permission** for existing admins
5. **Verifies migration** success

### 4. Test the Migration

After migration, verify:
- Admin accounts have reversal permission enabled
- You can see the "Reverse Loan" button on eligible loans
- The reversal process works through all safeguards

## Rollback (If Needed)

If you need to remove the loan reversal feature:

```bash
python rollback_loan_reversal.py
```

**⚠️ WARNING**: This will permanently delete all reversal data and cannot be undone!

## Manual Migration (Alternative)

If you prefer to run SQL manually:

### SQLite
```sql
ALTER TABLE staff ADD COLUMN reverse_loans_permission BOOLEAN DEFAULT 0;
ALTER TABLE loans ADD COLUMN reversed_at DATETIME;
ALTER TABLE loans ADD COLUMN reversed_by_id INTEGER;
ALTER TABLE loans ADD COLUMN reversal_reason TEXT;

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
);

UPDATE staff SET reverse_loans_permission = 1 WHERE role = 'admin';
```

### MySQL
```sql
ALTER TABLE staff ADD COLUMN reverse_loans_permission BOOLEAN DEFAULT 0;
ALTER TABLE loans ADD COLUMN reversed_at DATETIME;
ALTER TABLE loans ADD COLUMN reversed_by_id INTEGER;
ALTER TABLE loans ADD COLUMN reversal_reason TEXT;

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
);

UPDATE staff SET reverse_loans_permission = 1 WHERE role = 'admin';
```

## Post-Migration Configuration

After migration, you may want to:

1. **Review Admin Permissions**: Check which admins have reversal permission
2. **Set Permissions**: Use the Staff Accounts page to toggle reversal permission for specific admins
3. **Test Feature**: Create a test loan and verify the reversal process works

## Troubleshooting

### Migration Fails
- Check database connection in `.env` file
- Ensure you have write permissions on the database
- Verify database credentials for MySQL

### Permission Issues
- Ensure the database user has ALTER TABLE privileges
- For MySQL, the user may need CREATE, ALTER, and DROP privileges

### Rollback Issues
- SQLite rollback is complex due to column limitations
- Consider restoring from backup instead of rollback for SQLite

## Production Deployment

1. **Backup production database**
2. **Test migration on staging**
3. **Run migration during maintenance window**
4. **Verify migration success**
5. **Test reversal feature**
6. **Monitor for any issues**

## Support

If you encounter issues:
1. Check the error messages carefully
2. Verify your database connection
3. Ensure you have proper database permissions
4. Consider restoring from backup if migration fails