# Troniworld

The Ultimate Frisbee team platform: enhanced film viewing experience and team articles, inspired by Ultiworld.
<br>
Built for Tron, the Brandeis Men's Ultimate Frisbee team.

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
<img width="80%" height="80%" alt="Troniworld Article" src="https://github.com/user-attachments/assets/10b5b5b5-c6bc-46d7-a6f5-5cf25c70bfcd" />


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
