# Troniworld

The Ultimate Frisbee team platform: enhanced film viewing experience and team articles, inspired by Ultiworld.
<br>
Built for Tron, the Brandeis Men's Ultimate Frisbee team.

## Tech Stack

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Flask](https://img.shields.io/badge/Flask-000000?style=for-the-badge&logo=flask&logoColor=white)
![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-D71F00?style=for-the-badge&logo=sqlalchemy&logoColor=white)
![JavaScript](https://img.shields.io/badge/JavaScript-F7DF1E?style=for-the-badge&logo=javascript&logoColor=black)

# Features
### The Ultimate Film Experience

- Import games from Youtube
- Threadable team comments section - and notifications when you are mentioned
- View player sheets and point-specific information
	- Which players are on each point
	- O/D
	- Which team got the point?
- Saves viewing progress
- Easily see and skip to points you played
- Team and player based analytics

  
<img width="80%" height="80%" alt="Troniworld Home" src="https://github.com/user-attachments/assets/e872e6af-cd54-43e3-a83b-c5a7a3785d34" />
<img width="80%" height="80%" alt="Troniworld Game" src="https://github.com/user-attachments/assets/a3645b71-d9ea-442c-ae0f-a41f49b074e9" />
<img width="80%" height="80%" alt="Tronworld Data" src="https://github.com/user-attachments/assets/893fa092-09ab-4144-bca3-d2b193499d10" />

### Ultiworld-inspired Team Articles
- Postable by coaches and team admin
- Rich text editor
- Threadable comments
<img width="80%" height="80%" alt="Troniworld Article" src="https://github.com/user-attachments/assets/10b5b5b5-c6bc-46d7-a6f5-5cf25c70bfcd" />



# The Story
I was asked to build a Ultiworld inspired website for Tron, where coaches could post their own articles. However, I didn't stop there. Annoyed by the film watching experience, I wanted something better. Created over the span of a a few months, supported by Claude Code, Troniworld grew to have a film viewer with all the features I could want.

# Setup

Clone the repo
```bash
git clone https://github.com/liorschifrin/troniworld.git
cd troniworld
```

Create a .env file with
```
SECRET_KEY=""
DATABASE_URI="sqlite:///app.db"
```

Install dependencies
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

#### Create the database
For a new, empty database (the file named in `DATABASE_URI`, which must not already have tables):
```bash
flask --app app bootstrap-db
```
This creates every table from the current models and stamps the Alembic head, so later `flask db upgrade` runs start from the right place. It refuses to run against a database that already has any table. (The Alembic history cannot build a database from nothing: its first revision alters a `user` table that was created before Alembic was introduced. See `docs/orchestration/tasks/T07.md`.)

### Run
```bash
python app.py
```

#### Updating an existing DB
Back up the database file first (for SQLite, `sqlite3 app.db ".backup backup.db"` or copy the file while the app is stopped), then:
```bash
flask db upgrade
```
Databases stamped at `f65e956efdb9` or later upgrade to the head with their data preserved. Older stamps (`3cf0153b0d39` through `c9c8714eb81b`) cannot be upgraded by the shipped history; see the T07 task record before touching one. If an upgrade fails, restore the backup and stop; do not re-run it by hand. On SQLite the upgrade runs in one transaction and is rolled back if any foreign-key violation remains, leaving the database at its prior revision. Do not apply the offline `flask db upgrade --sql` output to SQLite with foreign keys on: it contains the table drops and would cascade-delete child rows (run it with `PRAGMA foreign_keys=OFF`, or prefer the online command).

After changing models.py, create a migration
```bash
flask db migrate -m "message"
flask db upgrade
```
Review the generated file before applying it. `python -m pytest tests/test_migrations.py` checks upgrades on temporary SQLite files and fails when the models and the migrated schema drift from the recorded list.
