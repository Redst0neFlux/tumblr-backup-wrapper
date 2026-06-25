from typing import Literal
import click
from pathlib import Path
from modules import database, user

PATH_TO_BACKUPS = Path("blogs")


@click.group()
def cli():
    """Blog management CLI."""
    pass


def search_for_blog(conn, query: str) -> list[str] | None:
    """
    Resolve a blog query to (uuid, blog_name).

    Returns None if not found; raises on interactive selection errors.
    """
    if query.startswith("t:"):
        return [query, query]

    # Try strict search first
    results: list[list[str]] = database.search_blog_names(conn, query, strict=True)
    if results:
        return results[0]

    # Fall back to non-strict search
    results: list[list[str]] = database.search_blog_names(conn, query, strict=False)
    if not results:
        return None

    if len(results) == 1:
        return results[0]

    # Multiple results - prompt user
    for idx, (_, name) in enumerate(results):
        click.echo(f"{idx}. {name}")

    selection: int = click.prompt("Select a blog from the list", type=int)
    if 0 <= selection < len(results):
        return results[selection]

    raise click.BadParameter(f"Invalid selection: {selection}")


@click.command()
@click.argument("query")
def search(query):
    """Search for blogs by name."""
    with database.initialize_db() as conn:
        results: list[list[str]] = database.search_blog_names(conn, query)

    if results:
        click.echo("Matching blogs:")
        for uuid, name in results:
            click.echo(f"{name} (UUID: {uuid})")
    else:
        click.echo("No matching blogs found.")


@click.command()
@click.argument("query")
@click.option(
    "--set", "should_set", is_flag=True, default=False, help="Set new options"
)
def config(query, should_set):
    """Get or set blog configuration options."""
    with database.initialize_db() as conn:
        result: list[str] | None = search_for_blog(conn, query)

        if result is None:
            click.echo("No matching blogs found.")
            return

        uuid, blog_name = result
        options: dict[str, list[str]] = database.get_blog_options(conn)

        # Display current options
        current_options: list[str] | Literal["No options set."] = options.get(
            uuid, "No options set."
        )
        click.echo(f"{blog_name}: {current_options}")

        # Set new options if requested
        if should_set:
            new_options: str = click.prompt(
                "Enter new options", type=str, default="", show_default=False
            )

            if new_options:
                options[uuid] = new_options.split()
            else:
                options.pop(uuid, None)

            database.save_blog_options(conn, options)
            click.echo(f"Saved options for {blog_name}: {new_options}")


@click.command()
@click.option(
    "--uuids",
    "show_uuids",
    is_flag=True,
    default=False,
    help="Display UUIDs for each blog",
)
def following(show_uuids: bool):
    """Get all currently followed blogs."""
    users: dict[str, str] = user.get_follows()
    if users:
        click.echo("Following blogs:")
        for uuid, name in users.items():
            if show_uuids:
                click.echo(f"{name} (UUID: {uuid})")
            else:
                click.echo(f"{name}")
    else:
        click.echo("Not following any blogs.")


@click.command()
@click.argument("query")
def unfollow(query: str):
    """Unfollow a blog."""
    users: dict[str, str] = user.get_follows()
    if query.startswith("t:"):
        to_unfollow: str = users[query]
    elif query in users.values():
        to_unfollow: str = query
    else:
        click.echo("Blog not found in following list.")
        return
    user.unfollow(to_unfollow)
    click.echo(f"Unfollowed {to_unfollow}.")


@click.command()
@click.argument("query")
def follow(query):
    """Follow a blog."""
    response: str = user.follow(query)
    if response:
        click.echo(response)
        click.echo(f"Followed {query} successfully.")
    else:
        click.echo(
            f"Failed to follow {query}. Please check the blog URL or your permissions."
        )


@click.command()
@click.option(
    "--uuids",
    "show_uuids",
    is_flag=True,
    default=False,
    help="Display UUIDs for each blog",
)
def backups(show_uuids):
    """List all backups on disk."""
    follows: dict[str, str] = user.get_follows()
    results: dict[str, list[str]] = {
        "Old": [],
        "Following": [],
        "Removed": [],
    }
    for path_object in PATH_TO_BACKUPS.iterdir():
        if path_object.is_dir() and path_object.name.startswith("t:"):
            with database.initialize_db() as conn:
                resp: list[list[str]] = database.search_blog_names(
                    conn, path_object.name, strict=True
                )
            if resp:
                current: list[str] = resp.pop(0)
                blog_name: str = (
                    current[1]
                    + (f" [{', '.join([x[1] for x in resp])}]" if resp else "")
                    + (" " + current[0] if show_uuids else "")
                )
                if current[0] not in follows:
                    results["Removed"].append(blog_name)
                else:
                    results["Following"].append(blog_name)
        else:
            results["Old"].append(path_object.name)
    for category, blogs in results.items():
        if not blogs:
            continue
        click.echo(f"{category}:")
        for blog in blogs:
            click.echo(f"  - {blog}")


cli.add_command(search)
cli.add_command(config)
cli.add_command(following)
cli.add_command(follow)
cli.add_command(unfollow)
cli.add_command(backups)

if __name__ == "__main__":
    cli()
