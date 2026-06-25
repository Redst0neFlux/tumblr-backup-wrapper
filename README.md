# tumblr-backup-wrapper

A lightweight Tumblr backup automation project that supports:
- backing up followed Tumblr blogs with `tumblr-backup`
- configuring per-blog backup options
- storing previous blog names and backup metadata in SQLite
- managing followed blogs from a Flask web UI
- managing followed blogs and backup options from a CLI

## Project structure

- `app.py` — Flask web application for managing tracked blogs and blog options
- `backup.py` — backup orchestration script that authenticates with Tumblr and runs `tumblr-backup`
- `cli.py` — command-line interface for managing followed blogs and editing options
- `modules/database.py` — SQLite helpers for blog metadata and option persistence
- `modules/user.py` — Tumblr API integration for follow/unfollow and retrieving followed blogs
- `templates/index.html` — Flask UI template
- `login.txt` — Tumblr login credentials for cookie-based auth
- `cookies.txt` — cookies file used by `tumblr-backup`
- `data.db` — SQLite database created by the app and backup script
- `lastrun.txt` — last backup summary report

## Requirements

This project requires Python 3.12 or later.

Dependencies are declared in `pyproject.toml` and include:
- `flask`
- `python-dotenv`
- `requests`
- `requests-oauth2client`
- `tumblr-backup[dash,jq,video]`

## Environment setup

### Option A: Use `uv` for Python environment management

If you have `uv` installed from [astral.sh](https://astral.sh/), use it to create and sync your Python environment:

```bash
uv sync
```

Then run commands through `uv`:

```bash
uv run backup.py
uv run app.py
uv run cli.py
```

### Option B: Use a plain virtual environment

```bash
python3 -m venv venv
source ./venv/bin/activate
python3 -m pip install .
```

### Environment variables with `.env`
1. Create a Tumblr OAuth application at `https://www.tumblr.com/oauth/apps`
2. Create a `.env` file in the project root with your Tumblr OAuth credentials and Flask secret (you can set this to any random string):

```text
TUMBLR_CLIENT_ID="..."
TUMBLR_CLIENT_SECRET="..."
SECRET_KEY="..."
```

This project uses `python-dotenv` to load those values automatically.

### Tumblr login credentials

Create `login.txt` with your Tumblr email/username and password on separate lines:

```text
email@example.com
password123
```

### Run the project

Run the Flask app or the backup script after the environment and `.env` file are set up.

## How it works

- `backup.py` reads `login.txt`, authenticates with Tumblr, saves cookies to `cookies.txt`, and invokes `tumblr-backup` for every followed blog.
- `modules/user.py` uses Tumblr OAuth2 credentials from environment variables to manage follow/unfollow operations and to retrieve the current following list.
- `modules/database.py` stores backup metadata and per-blog options in `data.db`.
- `app.py` and `cli.py` share the same SQLite database so data stays synchronized.

## Usage

### Run backups

```bash
python backup.py
```

### Run the web UI

```bash
python app.py
```

Then visit `http://localhost:5001`.

### Use the CLI

```bash
python cli.py search myblog
python cli.py config myblog --set
python cli.py following
python cli.py follow myblog
python cli.py unfollow myblog
python cli.py backups
```

## CLI commands

- `search <query>` — search tracked blogs by name or UUID
- `config <query>` — show current backup options for a tracked blog
- `config <query> --set` — interactively update the blog's options
- `following` — list blogs currently followed by the OAuth app owner
- `follow <query>` — follow a new Tumblr blog by URL or username
- `unfollow <query>` — unfollow an existing blog
- `backups` — list backup directories on disk and classify them by current following status

## Flask app behavior

- The web UI displays each followed blog and its configured options.
- You can save per-blog options or unfollow blogs from the browser.
- You can also follow a new blog from the top form.

## Database and storage

- `data.db` stores two tables:
  - `previous_names` — historical blog names and last backup timestamps
  - `blog_options` — per-blog backup option lists stored as JSON text
- `cookies.txt` is created during backup authentication and reused by `tumblr-backup`.
- `lastrun.txt` contains the summary of the most recent backup run.
