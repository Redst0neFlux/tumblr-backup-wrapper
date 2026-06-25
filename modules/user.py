"""Tumblr API helpers for follow management.

This module provides authenticated Tumblr API calls to:
- retrieve the current user's following list
- follow a blog by URL or username
- unfollow a followed blog

The session is authenticated using OAuth2 client credentials loaded from
environment variables via `.env`.
"""

import os

import requests
from dotenv import load_dotenv
from requests_oauth2client import OAuth2Client, OAuth2ClientCredentialsAuth
from modules import database

load_dotenv()

oauth2client = OAuth2Client(
    token_endpoint="https://api.tumblr.com/v2/oauth2/token",
    client_id=os.environ.get(key="TUMBLR_CLIENT_ID", default=""),
    client_secret=os.environ.get(key="TUMBLR_CLIENT_SECRET", default=""),
)

session = requests.Session()
session.auth = OAuth2ClientCredentialsAuth(oauth2client, scope="basic write")


def get_blog_name() -> str:
    """Return the authenticated user's Tumblr blog name."""
    resp: requests.Response = session.get("https://api.tumblr.com/v2/user/info")
    return resp.json()["response"]["user"]["name"]


def get_follows() -> dict[str, str]:
    """Return a mapping of followed blog UUIDs to blog names."""
    following: dict[str, str] = {}
    offset = 0
    while True:
        response: requests.Response = session.get(
            "https://api.tumblr.com/v2/user/following", params={"offset": offset}
        )
        if offset > response.json()["response"]["total_blogs"]:
            break
        offset += 20

        to_add: dict[str, str] = {
            blog["uuid"]: blog["name"] for blog in response.json()["response"]["blogs"]
        }

        following: dict[str, str] = to_add | following

    return following


def follow(to_follow) -> str:
    """Follow a Tumblr blog and record its UUID in the local database."""
    response: requests.Response = session.post(
        "https://api.tumblr.com/v2/user/follow", data={"url": to_follow}
    )
    if response.status_code != 200:
        return ""

    uuid: str = response.json()["response"]["blog"]["uuid"]
    with database.initialize_db() as conn:
        database.upsert_previous_name(conn, uuid, to_follow)

    return uuid


def unfollow(to_unfollow) -> requests.Response:
    """Unfollow a Tumblr blog by URL or username."""
    response: requests.Response = session.post(
        "https://api.tumblr.com/v2/user/unfollow", data={"url": to_unfollow}
    )
    return response
