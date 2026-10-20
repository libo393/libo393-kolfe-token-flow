# Token Redemption App

A starter-ready Flask application for employee token balances, QR identification, merchant deductions, Excel/CSV imports, and transaction reports.

## Requirements
- Python 3.10+
- pip

## Run locally
```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate
pip install -r requirements.txt
python server.py
```
Open http://127.0.0.1:5000

## First login
- Username: `admin`
- Password: `Admin123!`

**Change the default admin password immediately** using the Change password form after logging in. Set a strong `SECRET_KEY` environment variable before deployment.

## Roles
- **Admin:** create employee/merchant accounts, allocate tokens, import employee records, view users and transactions, download CSV report.
- **Merchant:** enter the employee code read from the QR and deduct tokens.
- **Employee:** view balance, QR code, and redemption history.

## Excel / CSV import
Upload `.xlsx` or `.csv` with columns:
- `username` (required)
- `full_name` or `name` (required)
- `employee_code` (optional; generated if absent)
- `balance` (optional; defaults to 0)
- `password` (optional; defaults to `ChangeMe123!`)

Imported default passwords should be changed by the account holders. Duplicate usernames/codes are skipped. Only employee rows are imported.

## QR scanner note
This build generates QR codes containing a stable employee identifier. The merchant screen accepts that code manually, so it works on desktop and mobile without camera permissions. To enable automatic camera scanning, integrate a maintained browser QR library and test camera permissions/HTTPS on target devices.

## Production checklist
This is a functional starter, not a security-audited production deployment. Before real use:
- Set a random `SECRET_KEY`, use HTTPS, and disable debug mode.
- Replace the default admin password and default import password policy.
- Add CSRF protection, rate limiting, audit logging, backups, and automated tests.
- Consider PostgreSQL and migrations for multiple app instances.
- Review local privacy, financial, and employment requirements.
- Back up `database.db`; it contains account and transaction data.

SQLite database and QR images are created automatically on first run. Do not commit real database contents to source control.
