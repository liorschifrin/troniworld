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

### Run
```bash
python app.py
```

#### Updating the DB
After changing models.py, create a migration
```bash
flask db migrate -m "message"
flask db upgrade
```
