# SkyShelf

SkyShelf is a cloud-based file sharing system in Python, inspired by a mini Google Drive. It includes user accounts, private uploads, downloadable files, and public share links that can be toggled on or off from the dashboard.

## Features

- User registration and login
- Private file uploads with local server storage
- Personal dashboard with storage stats
- Download files you own
- Create public share links
- Revoke a share link at any time
- Delete uploaded files
- MySQL database that you can inspect and manage from MySQL Workbench

## Project Structure

```text
.
|-- app.py
|-- mysql_schema.sql        # optional schema script for MySQL Workbench
|-- requirements.txt
|-- storage/uploads/        # uploaded files are stored here
|-- static/
|   |-- css/styles.css
|   `-- js/app.js
`-- templates/
    |-- base.html
    |-- dashboard.html
    |-- index.html
    |-- login.html
    |-- not_found.html
    |-- register.html
    `-- share.html
```

## Setup

1. Make sure MySQL Server is running on your machine and that you can connect to it from MySQL Workbench.

2. Create a virtual environment:

   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```

3. Install dependencies:

   ```powershell
   pip install -r requirements.txt
   ```

4. Set your MySQL connection details:

   ```powershell
   $env:DB_HOST="localhost"
   $env:DB_PORT="3306"
   $env:DB_USER="root"
   $env:DB_PASSWORD="your-mysql-password"
   $env:DB_NAME="skyshelf"
   $env:SECRET_KEY="replace-this-before-production"
   ```

5. Run the app:

   ```powershell
   python app.py
   ```

   On startup, the app creates the database and tables automatically if they do not already exist.

6. Open the local URL shown in the terminal, usually:

   ```text
   http://127.0.0.1:5000
   ```

## Environment Variables

- `SECRET_KEY`: recommended for anything beyond local demo usage
- `DB_HOST`: MySQL host, usually `localhost`
- `DB_PORT`: MySQL port, usually `3306`
- `DB_USER`: MySQL username
- `DB_PASSWORD`: MySQL password
- `DB_NAME`: database name to create/use, default `skyshelf`

Example:

```powershell
$env:DB_HOST="localhost"
$env:DB_PORT="3306"
$env:DB_USER="root"
$env:DB_PASSWORD="your-mysql-password"
$env:DB_NAME="skyshelf"
$env:SECRET_KEY="replace-this-before-production"
python app.py
```

## MySQL Workbench

- Open MySQL Workbench and connect to the same server defined by your `DB_HOST`, `DB_PORT`, `DB_USER`, and `DB_PASSWORD`.
- You can let the app create the schema automatically, or open [mysql_schema.sql](</c:/Users/dell/Desktop/New folder (4)/mysql_schema.sql>) in Workbench and run it manually.
- If you change `DB_NAME`, update the database name inside `mysql_schema.sql` before running it manually.

## Notes

- Maximum upload size is currently 50 MB per file.
- Uploaded files are stored on the local disk in `storage/uploads`.
- This is a strong starter project for learning or demos. For production, you would typically add:
  - object storage like AWS S3
  - email/password recovery
  - role-based permissions
  - background virus scanning
  - CSRF protection and more hardened security controls
