# troniworld
An Ultiworld clone for Tron

## Flask + SQLAlchemy boilerplate

### Setup

Create a .env file with
```
SECRET_KEY=""
DATABASE_URI="sqlite:///app.db"
```

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Run
```bash
python app.py
```

### Updating the DB
After changing models.py, create a migration
```bash
flask db migrate -m "message"
flask db upgrade
```