"""Flask application for managing follow state and tumblr-backup options.

This module provides a small web UI that lists followed blogs, allows
saving backup options per blog, and enables following/unfollowing blogs.
"""

import os
import secrets

from flask import Flask, redirect, render_template, request, url_for

from modules import database, user

APP_ROOT: str = os.path.dirname(__file__)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or secrets.token_hex(32)


def load_blog_options() -> dict[str, list[str]]:
    """Load the saved blog option mapping from the SQLite database.

    Returns an empty dictionary when the options cannot be loaded.
    """
    try:
        with database.initialize_db() as conn:
            return database.get_blog_options(conn)
    except Exception:
        return {}


def save_blog_options(blog_options: dict[str, list[str]]) -> None:
    """Persist the current per-blog options mapping into the SQLite database."""
    with database.initialize_db() as conn:
        database.save_blog_options(conn, blog_options)


def build_blog_forms(
    following: dict[str, str], blog_options: dict[str, list[str]]
) -> str:
    """Build HTML form fragments for each followed blog.

    The generated HTML is rendered directly in the template via the
    `blog_forms` placeholder.
    """
    sections: list[str] = []

    for uuid, display in following.items():
        options: str = " ".join(blog_options.get(uuid, []))
        sections.append(
            f"""
            <form action="{url_for("index")}" method="post">
              <input type="hidden" name="uuid" value="{uuid}" />
              <label for="options_{uuid}">{display}</label><br />
              <input type="text" id="options_{uuid}" name="options" value="{options}" />
              <button type="submit" name="action" value="save">Save</button>
              <button type="submit" name="action" value="unfollow">Unfollow</button>
            </form>
            """
        )

    return "\n".join(sections)


def process_post(form_data: dict[str, str], blog_options: dict[str, list[str]]) -> None:
    """Handle form submissions from the web UI.

    Supports following a new blog, unfollowing an existing blog, and saving
    per-blog backup options.
    """
    follow_username: str = form_data.get("_follow", "").strip()
    if follow_username:
        uuid: str | bool = user.follow(to_follow=follow_username)
        if not uuid:
            raise
        with database.initialize_db() as conn:
            database.upsert_previous_name(
                conn, uuid, follow_username,
            )
        return

    action: str | None = form_data.get("action")
    uuid: str = form_data.get("uuid", "").strip()

    if action == "unfollow" and uuid:
        user.unfollow(uuid)
        return

    if action == "save" and uuid:
        blog_options[uuid] = form_data.get("options", "").split()
        save_blog_options(blog_options)


@app.route("/", methods=["GET", "POST"])
def index():
    """Home page."""
    blog_options: dict[str, list[str]] = load_blog_options()

    if request.method == "POST":
        process_post(request.form, blog_options)
        return redirect(url_for("index"))

    following: dict[str, str] = user.get_follows()
    blog_forms: str = build_blog_forms(following, blog_options)

    return render_template("index.html", blog_forms=blog_forms)



if __name__ == "__main__":
    app.run(debug=True, host="localhost", port=5001)
