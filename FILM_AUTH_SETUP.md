# Film Authentication System - Setup & Usage Guide

## Overview
The film side of Troniworld now has separate authentication from the blog. All film routes require authentication, and users are redirected to a film-specific login page if not authenticated.

## Environment Setup

### 1. Configure .env file
Add these variables to your `.env` file (already added):

```env
FILM_USER_PASSWORD="your_user_password_here"
FILM_ADMIN_PASSWORD="your_admin_password_here"
```

**Update these passwords to your desired values before creating users!**

### 2. Database Migration
The database has already been migrated with the following changes:
- Added `is_leadership` field to User
- Added `is_film_user` field to User  
- Added `player_id` field to User (foreign key to Player)

## Creating Film Users

### Option 1: Initial Setup (First Admin)
**When no admin exists yet:**
1. Start the Flask application: `flask run`
2. Navigate to `/film/setup` in your browser
3. Enter a username for the first admin
4. Optionally select an associated player
5. Click "Create Admin User"
6. You'll be redirected to login
7. Login with your username and the `FILM_ADMIN_PASSWORD` from .env

**Note:** The `/film/setup` route is only accessible when no film admin exists. Once the first admin is created, this route redirects to login.

### Option 2: Admin Panel (After First Admin Exists)
1. Login at `/film/login` with your admin account
2. Navigate to `/film/admin/users`
3. Use the web interface to:
   - Create individual users
   - Bulk create users for all players
   - Manage existing users

### Option 3: Manual Creation (Advanced)
To create users manually using the Flask shell:

```python
# Run: flask shell
from flask_app import db
from flask_app.models import User
from werkzeug.security import generate_password_hash
import os

# Load .env
from dotenv import load_dotenv
load_dotenv()

# Create first admin
admin = User(
    username='admin',  # Change this
    hashed_password=generate_password_hash(os.getenv('FILM_ADMIN_PASSWORD')),
    is_admin=True,
    is_leadership=True,
    is_film_user=True,
    player_id=None  # Or link to a player
)
db.session.add(admin)
db.session.commit()
print(f"Admin user '{admin.username}' created!")
```

## User Roles

### Admin Users
- Can access all film routes
- Can create/edit/delete games
- Can upload CSV game data
- Can delete player sheets
- Can manage film users at `/film/admin/users`
- Use `FILM_ADMIN_PASSWORD` to login

### Regular Users
- Can view all games and film content
- Can add comments
- Cannot create/edit games
- Cannot delete content
- Use `FILM_USER_PASSWORD` to login

### Leadership Users
- Same as regular users currently
- Future feature flag for additional permissions
- Use `FILM_USER_PASSWORD` to login

## Film Routes

### Public (No Auth Required)
- `/film/login` - Film login page

### Authenticated Routes (Any Film User)
- `/player` - Film room home
- `/games` - List of all games
- `/games/<id>` - View specific game with player sheet
- `/api/games/<id>/comments` - Get/post comments

### Admin-Only Routes
- `/film/games/new_game` - Create new game
- `/games/<id>/edit` - Edit game details
- `/games/<id>/upload_csv` - Upload game data CSV
- `/games/<id>/delete_player_sheet` - Delete player sheet data
- `/film/admin/users` - Manage film users
- `/api/games/<id>/comments/<id>` (DELETE) - Delete comments
- `/api/games/<id>/points/<id>` (PATCH) - Update point details

## How It Works

### Authentication Flow
1. User visits any film route (e.g., `/games`)
2. If not authenticated, redirected to `/film/login?next=/games`
3. User enters username and password
4. System checks:
   - User exists and `is_film_user=True`
   - Password matches role-based shared password
5. On success, user redirected to original page
6. Session stores `film_user_id` (separate from blog's `user_id`)

### Shared Passwords
- All regular users share `FILM_USER_PASSWORD`
- All admin users share `FILM_ADMIN_PASSWORD`
- Passwords are hashed in the database
- Users only need to remember their username

### Player Association
- Each User can optionally link to a Player
- Most players will have associated users
- Coaches/staff may not have player associations
- Bulk creation automatically links by matching names

## Template Updates
Film templates now use `current_user` from `get_current_film_user()` instead of the blog's user context.

## Logout
Users can logout at `/film/logout`, which clears their film session and redirects to the login page.

## Security Notes
- Film authentication is separate from blog authentication
- Session-based auth (existing Flask sessions)
- Shared passwords stored in `.env` (not in database)
- All passwords are hashed with werkzeug.security
- Admin routes double-protected (auth + admin check via decorator)

## Testing the System

1. **Set passwords in .env**
   ```bash
   # Edit .env and update:
   FILM_USER_PASSWORD="your_chosen_password"
   FILM_ADMIN_PASSWORD="your_admin_password"
   ```

2. **Create first admin user**
   ```bash
   flask shell
   # Then run the manual creation script above
   ```

3. **Login**
   - Visit `/film/login`
   - Enter username and password
   - Should redirect to film room

4. **Create more users**
   - Login as admin
   - Visit `/film/admin/users`
   - Create users via web interface

## Troubleshooting

**"Invalid username or password"**
- Check that user has `is_film_user=True`
- Verify password matches role's shared password in .env
- Ensure .env file is loaded

**"You must be an admin"**
- User needs `is_admin=True` for admin routes
- Check user in database: `User.query.filter_by(username='...').first()`

**Redirected to login constantly**
- Check session is working
- Verify `film_user_id` is set in session
- Clear browser cookies and try again

**Can't access admin panel**
- User must have both `is_film_user=True` AND `is_admin=True`
- Check with: `User.query.get(id)` in Flask shell
