# Movie Reservation System

A learning project based on https://roadmap.sh/projects/movie-reservation-system.

## Local tools

- Python 3.11 with a project virtual environment in `.venv`.
- Django 5.2 and Psycopg (the PostgreSQL Python driver).
- PostgreSQL 17, with server and command-line tools.

Run Python through the virtual environment in PowerShell:

```powershell
.\.venv\Scripts\python.exe --version
.\.venv\Scripts\python.exe -m django --version
```

To recreate the Python environment:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Local database connection settings, including the generated password for the
`postgres` administrator, are in `.env`. This file is excluded from Git. Do not
share it. `.env.example` documents the fields without the password. Django does
not automatically load this file; connection configuration will be added when
we create the application. A separate application database and user should be
created then.

The PostgreSQL command-line tools are normally installed under
`C:\Program Files\PostgreSQL\17\bin`. The database server runs as a Windows
service. pgAdmin and Stack Builder are not required and are not installed.

The application itself has not been created yet.
