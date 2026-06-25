"""Tumblr backup automation script.

This script handles:
- Authenticating with Tumblr
- Fetching blogs being followed
- Backing up each blog with appropriate options
"""

import sys
from http.cookiejar import MozillaCookieJar
from multiprocessing import set_start_method

from requests import Session
from tumblr_backup.login import tumblr_login
from tumblr_backup.main import main as tumblr_backup

from modules import database, user

# Constants
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/94.0.4606.71 Safari/537.36"
)
COOKIES_FILE = "cookies.txt"
LOGIN_FILE = "login.txt"
BACKUP_ARGS: list[str] = [
    "--incremental",
    # "--tag-index",
    "--cookiefile",
    COOKIES_FILE,
    "--outdir", # Blog uuid will be added as additional argument later
]


def read_login_credentials() -> tuple[str, str]:
    """Read Tumblr login credentials from login.txt.

    File format:
        emailaddress@example.org
        password123

    Returns:
        Tuple of (login, password)

    Raises:
        FileNotFoundError: If login.txt does not exist
        ValueError: If login.txt doesn't contain exactly 2 lines
    """
    with open(file=LOGIN_FILE, mode="r") as loginfile:
        lines: list[str] = [x.rstrip() for x in loginfile]
        if len(lines) != 2:
            raise ValueError(f"Expected 2 lines in {LOGIN_FILE}, got {len(lines)}")
        return lines[0], lines[1]


def authenticate_and_save_cookies() -> None:
    """Authenticate with Tumblr and save cookies to file."""
    login: str
    password: str
    login, password = read_login_credentials()
    with Session() as session:
        session.headers["User-Agent"] = USER_AGENT
        session.cookies = MozillaCookieJar(filename=COOKIES_FILE)
        tumblr_login(session, login, password)
        session.cookies.save(ignore_discard=True)


def setup_multiprocessing() -> None:
    """Configure multiprocessing for tumblr_backup.

    This prevents tumblr_backup from starting its own forkserver,
    which would crash if called multiple times.
    """
    set_start_method(method="forkserver")
    sys.modules["multiprocessing"].set_start_method = lambda _: True  # ty:ignore[unresolved-attribute]
    tumblr_backup.__globals__["root_folder"] += "/blogs"


def build_backup_args(uuid: str, blog_options: dict) -> list[str]:
    """Build command-line arguments for tumblr_backup.

    Args:
        uuid: Blog UUID
        blog_options: Dictionary of UUID to options mapping

    Returns:
        List of command-line arguments
    """
    args: list[str] = BACKUP_ARGS + [uuid]
    if uuid in blog_options:
        args.extend(blog_options[uuid])
    return args


def backup_blog(uuid: str, blog_name: str, blog_options: dict) -> int:
    """Backup a single blog.

    Args:
        blog: Blog info dict with 'uuid' and 'name' keys
        blog_options: Dictionary of UUID to options mapping

    Returns:
        Exit code from tumblr_backup
    """
    args: list[str] = build_backup_args(uuid, blog_options)
    authenticate_and_save_cookies() # Regenerate cookies each time to avoid expiration issues
    sys.argv = ["tumblr_backup"] + args + [blog_name]
    return tumblr_backup()


def process_backup_result(
    exit_code: int,
    uuid: str,
    blog_name: str,
    results: dict[str, int],
    failed_blogs: list[str],
    conn,
) -> None:
    """Process and log the result of a blog backup.

    Args:
        exit_code: Exit code from tumblr_backup
        uuid: Blog UUID
        blog_name: Blog name
        results: Dictionary tracking success/failure counts
        failed_blogs: List to accumulate failed blog names
        conn: SQLite connection to previous names database
    """
    match exit_code:
        case 0 | 5:
            results["Success"] += 1
            print(f"{blog_name}: Success")
            database.upsert_previous_name(conn, uuid, blog_name)
        case 4 | 1:
            results["Failure"] += 1
            failed_blogs.append(f"{blog_name}: {uuid}")
            print()
            print(f"{blog_name}: Failure")
    print("----------------------")


def report_backup_results(results: dict[str, int], failed_blogs: list[str]) -> None:
    """Print summary of backup results.

    Args:
        results: Dictionary with 'Success' and 'Failure' counts
        failed_blogs: List of failed blog names with UUIDs
    """
    output: str = repr(results) + "\n"
    if failed_blogs:
        output += "Failed blogs:\n"
        output += "- " + "\n- ".join(failed_blogs)
    print(output)
    with open(file="lastrun.txt", mode="w") as lastrun:
        lastrun.write(output)


def backup_following_blogs(
    blog_options: dict, connection
) -> dict[str, dict[str, int] | list[str]]:
    """Backup all blogs in the following list.

    Args:
        blog_options: Dictionary of UUID to options mapping
        conn: SQLite connection storing previous names

    Returns:
        Dictionary with 'results' and 'failed_blogs' keys
    """
    following: dict = user.get_follows()
    print(following)
    results: dict[str, int] = {"Success": 0, "Failure": 0}
    failed_blogs: list[str] = []

    blogs_to_backup: list[tuple[str, str, str | None]] = []
    for uuid, blog_name in following.items():
        last_backup: str | None = database.get_last_backup_timestamp(connection, uuid)
        blogs_to_backup.append((uuid, blog_name, last_backup))

    blogs_to_backup.sort(key=lambda item: (item[2] is not None, item[2] or ""))

    num_blogs: int = len(blogs_to_backup)
    for i in range(num_blogs):
        uuid, blog_name, _ = blogs_to_backup[i]
        print(f"Beginning backup of: {blog_name} ({i + 1}/{num_blogs})")
        exit_code: int = backup_blog(uuid, blog_name, blog_options)
        process_backup_result(
            exit_code, uuid, blog_name, results, failed_blogs, connection
        )

    return {
        "results": results,
        "failed_blogs": failed_blogs,
    }


def main() -> None:
    """Main backup orchestration."""
    setup_multiprocessing()
    with database.initialize_db() as conn:
        # Ensure any existing blogoptions.json is migrated into the DB
        blog_options: dict = database.get_blog_options(conn)
        backup_data: dict = backup_following_blogs(
            blog_options=blog_options, connection=conn
        )
    report_backup_results(
        results=backup_data["results"], failed_blogs=backup_data["failed_blogs"]
    )


if __name__ == "__main__":
    main()
