# Movie Reservation System

A Django and PostgreSQL learning project based on:
https://roadmap.sh/projects/movie-reservation-system

## Features

- User signup, login, and logout.
- Movies, genres, auditoriums, seats, and showtimes.
- Movie and screening browsing with date filtering.
- Movie detail pages display poster images and assigned genres.
- Seat availability and authenticated booking.
- Personal reservation history and cancellation.
- Ticket prices preserved at booking.
- Database protection against double booking.
- Admin scheduling validation for overlapping screenings.
- Staff-only capacity and booking-value reports.
- Cinema admin group with restricted permissions.

Payments are not processed. Reports show recorded booking value,
excluding cancelled reservations. Historical reservations without a
recorded price are reported separately.

## Requirements

- Python 3.11.
- PostgreSQL 17.
- Git.

## Installation

Clone the repository and enter its folder:

```powershell
git clone https://github.com/BrianChen809/movie-reservation-system.git
cd movie-reservation-system
```

Create a virtual environment and install dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

## Database setup

Open PostgreSQL's terminal:

```powershell
& "C:\Program Files\PostgreSQL\17\bin\psql.exe" -U postgres -d postgres
```

Enter the PostgreSQL administrator password when prompted.

Create an application account and database. Replace the example password
with your own password:

```sql
CREATE USER movie_app WITH PASSWORD 'replace-with-your-password';
CREATE DATABASE movie_reservation OWNER movie_app;
```

For local automated testing, allow the account to create a test database:

```sql
ALTER USER movie_app CREATEDB;
```

Exit PostgreSQL's terminal:

```text
\q
```

Create the local configuration file:

```powershell
Copy-Item .env.example .env
```

Edit `.env` to match your database:

```dotenv
PGHOST=localhost
PGPORT=5432
PGUSER=movie_app
PGPASSWORD=replace-with-your-password
PGDATABASE=movie_reservation
```

Never commit `.env`. It contains your local database password and is
excluded by `.gitignore`.

## Initialize the application

Create the database tables and cinema admin group:

```powershell
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py setup_roles
```

Create the initial Django superuser:

```powershell
.\.venv\Scripts\python.exe manage.py createsuperuser
```

This website account is separate from PostgreSQL database accounts.

## Run locally

```powershell
.\.venv\Scripts\python.exe manage.py runserver
```

- Movie list: http://127.0.0.1:8000/movies/
- Django admin: http://127.0.0.1:8000/admin/
- Staff report: http://127.0.0.1:8000/movies/reports/screenings/

Press Ctrl+C in the terminal to stop the server.

## Add sample data

Sign in to the Django admin as the superuser and create:

1. A genre and a movie with a duration.
2. An auditorium.
3. Seats belonging to that auditorium.
4. A future showtime with a movie, auditorium, and ticket price.

Create a regular account through the public signup page, then use it
to book a seat.

## Cinema administrators

Run `setup_roles` to create or update the Cinema admins group.

Using the superuser account, edit a user's account in the admin:

- Enable Staff status.
- Add the account to Cinema admins.
- Leave Superuser status disabled.

Cinema admins can manage cinema records and access reports. The group
does not grant permission to manage users or groups.

Running `setup_roles` again preserves existing group members and resets
the group's permissions to the project's intended cinema permissions.

## Tests

```powershell
.\.venv\Scripts\python.exe manage.py test movies
```

Django creates and removes a separate test database. Do not configure
a shared or production database for these tests.

Tests cover booking, cancellation, ownership, permissions, reports,
scheduling validation, reservation prices, and simultaneous booking.

## Important behavior and limitations

- Each reservation represents one seat.
- Only upcoming active reservations can be cancelled.
- Cancelled reservations remain in booking history.
- Existing reservations cannot be reassigned or deleted through the admin.
- Seats with reservation history cannot be moved or renamed through
  admin forms.
- Screenings with reservation history cannot change movie, auditorium,
  or start time through admin forms, including when all bookings were cancelled.
  Create a new screening instead. Ticket prices remain editable for future
  bookings; existing reservations keep their recorded prices.
- Movie duration cannot change through admin forms once showtimes exist.
- Scheduling validation runs through model validation; direct database
  updates can bypass it.
- Simultaneous scheduling requests are not protected by a database
  overlap constraint.
- Staff report access currently depends on Staff status.
- This is a local development project. Production deployment requires
  a separate configuration review.

Application code and migrations are tracked by Git. Users, movies,
permissions, and reservations are stored separately in PostgreSQL.
Pushing to GitHub does not upload those database records.
