#!/usr/bin/env python3
import asyncio
import json
import os
from pathlib import Path
from urllib.parse import urlparse

import httpx
from twscrape import API
from twscrape.accounts_pool import AccountsPool
from twscrape.api import GQL_FEATURES, GQL_URL, OP_UserByScreenName
from twscrape.models import parse_user
from twscrape.queue_client import AbortReqError, Ctx, XClIdGenStore
from twscrape.utils import encode_params

TARGET_ACCOUNTS = [
    "Barchart",
    "rickjeff78",
    "LizAnnSonders",
    "AAIISentiment",
    "HFI_Research",
    "neilksethi",
    "spotgamma",
    "MenthorQpro",
    "zerohedge",
]
SEARCH_TERMS = ["CTA-s", "CTAs"]
SEARCH_LIMIT = 40
MIN_LIKES = 5

BASE_DIR = Path.home() / ".macro_dashboard"
DB_PATH = BASE_DIR / "accounts.db"
IMAGES_DIR = BASE_DIR / "chart_images"
POSTS_PATH = BASE_DIR / "x_intel_posts.json"
POOL = AccountsPool(str(DB_PATH))


_ORIG_CTX_REQ = Ctx.req


async def _safe_ctx_req(self, method: str, url: str, params=None):
    path = urlparse(url).path or "/"

    tries = 0
    while tries < 3:
        headers = {}
        try:
            gen = await XClIdGenStore.get(self.acc.username, fresh=tries > 0)
            token = gen.calc(method, path)
            if token:
                headers["x-client-transaction-id"] = token
        except Exception:
            # X changes the public page structure frequently, which breaks
            # twscrape's x-client-transaction-id bootstrap. The authenticated
            # GraphQL request still works without that header for our use case.
            headers = {}

        rep = await self.clt.request(method, url, params=params, headers=headers)
        if rep.status_code != 404:
            return rep

        tries += 1
        await asyncio.sleep(1)

    raise AbortReqError("Failed to complete request after x-client-transaction-id retries")


Ctx.req = _safe_ctx_req


async def resolve_user(api: API, handle: str):
    accounts = await POOL.get_all()
    active_accounts = [account for account in accounts if account.active]
    if not active_accounts:
        raise RuntimeError("No active twscrape accounts available for fallback user lookup")

    account = active_accounts[0]
    client = account.make_client()
    try:
        params = {
            "variables": {"screen_name": handle, "withSafetyModeUserFields": True},
            "features": {
                **GQL_FEATURES,
                "highlights_tweets_tab_ui_enabled": True,
                "hidden_profile_likes_enabled": True,
                "creator_subscriptions_tweet_preview_api_enabled": True,
                "hidden_profile_subscriptions_enabled": True,
                "subscriptions_verification_info_verified_since_enabled": True,
                "subscriptions_verification_info_is_identity_verified_enabled": False,
                "responsive_web_twitter_article_notes_tab_enabled": False,
                "subscriptions_feature_can_gift_premium": False,
                "profile_label_improvements_pcf_label_in_post_enabled": False,
            },
        }
        response = await client.get(
            f"{GQL_URL}/{OP_UserByScreenName}",
            params=encode_params(params),
        )
        response.raise_for_status()
        return parse_user(response.json())
    finally:
        await client.aclose()


def get_target_accounts() -> list[str]:
    override = os.getenv("X_TARGET_ACCOUNTS", "").strip()
    if not override:
        return TARGET_ACCOUNTS
    accounts = [item.strip().lstrip("@") for item in override.split(",") if item.strip()]
    return accounts or TARGET_ACCOUNTS


def get_search_terms() -> list[str]:
    override = os.getenv("X_SEARCH_TERMS", "").strip()
    if not override:
        return SEARCH_TERMS
    terms = [item.strip() for item in override.split(",") if item.strip()]
    return terms or SEARCH_TERMS


def load_existing_posts() -> dict[tuple[str, int], dict]:
    if not POSTS_PATH.exists() or POSTS_PATH.stat().st_size == 0:
        return {}

    try:
        existing = json.loads(POSTS_PATH.read_text(encoding="utf-8")) or []
    except Exception:
        return {}

    return {
        (str(item.get("source_account", "")).lower(), int(item.get("id"))): item
        for item in existing
        if item.get("id") is not None and item.get("source_account")
    }


def merge_posts(existing_map: dict[tuple[str, int], dict], new_posts: list[dict]) -> list[dict]:
    merged = dict(existing_map)
    for item in new_posts:
        merged[(str(item.get("source_account", "")).lower(), int(item["id"]))] = item

    def sort_key(item: dict):
        return (
            str(item.get("created_at", "")),
            int(item.get("likes") or 0),
            int(item.get("retweets") or 0),
        )

    return sorted(merged.values(), key=sort_key, reverse=True)


async def download_photo(client: httpx.AsyncClient, url: str, destination: Path) -> str:
    if destination.exists():
        return str(destination)

    response = await client.get(url, follow_redirects=True, timeout=30)
    response.raise_for_status()
    destination.write_bytes(response.content)
    return str(destination)


def _photo_urls_from_tweet(tweet) -> list[str]:
    media = getattr(tweet, "media", None)
    return [photo.url for photo in list(getattr(media, "photos", []) or []) if getattr(photo, "url", None)]


def _serialize_tweet_context(tweet) -> dict | None:
    if tweet is None:
        return None
    return {
        "author": getattr(getattr(tweet, "user", None), "username", ""),
        "text": getattr(tweet, "rawContent", "") or "",
        "media_urls": _photo_urls_from_tweet(tweet),
    }


async def fetch_replies(api: API, client: httpx.AsyncClient, tweet_id: int) -> list[dict]:
    replies: list[dict] = []
    await asyncio.sleep(1)
    async for reply in api.tweet_replies(tweet_id, limit=10):
        reply_image_paths: list[str] = []
        for index, photo_url in enumerate(_photo_urls_from_tweet(reply), start=1):
            destination = IMAGES_DIR / f"{reply.id}_{index}.jpg"
            try:
                reply_image_paths.append(await download_photo(client, photo_url, destination))
            except Exception as exc:
                print(f"Failed to download reply image for tweet {reply.id}: {exc}")

        replies.append(
            {
                "id": reply.id,
                "author_handle": reply.user.username,
                "author_name": reply.user.displayname,
                "author_followers": reply.user.followersCount,
                "text": reply.rawContent,
                "likes": reply.likeCount,
                "image_paths": reply_image_paths,
            }
        )
    return replies


async def build_post_record(
    api: API,
    client: httpx.AsyncClient,
    tweet,
    *,
    source_account: str,
    discovery_query: str | None = None,
) -> dict | None:
    if int(tweet.likeCount or 0) < MIN_LIKES:
        return None

    media = getattr(tweet, "media", None)
    photos = list(getattr(media, "photos", []) or [])
    if not photos:
        return None

    image_paths: list[str] = []
    for index, photo in enumerate(photos, start=1):
        destination = IMAGES_DIR / f"{tweet.id}_{index}.jpg"
        try:
            image_paths.append(await download_photo(client, photo.url, destination))
        except Exception as exc:
            print(f"Failed to download image for tweet {tweet.id}: {exc}")

    if not image_paths:
        return None

    try:
        replies = await fetch_replies(api, client, tweet.id)
    except Exception as exc:
        print(f"Failed to fetch replies for tweet {tweet.id}: {exc}")
        replies = []

    parent_tweet = None
    if getattr(tweet, "inReplyToTweetId", None):
        try:
            parent_tweet = _serialize_tweet_context(await api.tweet_details(tweet.inReplyToTweetId))
        except Exception as exc:
            print(f"Failed to fetch parent tweet for tweet {tweet.id}: {exc}")

    quoted_tweet = None
    try:
        quoted_tweet = _serialize_tweet_context(getattr(tweet, "quotedTweet", None))
    except Exception:
        quoted_tweet = None

    return {
        "id": tweet.id,
        "author_handle": tweet.user.username,
        "author_name": tweet.user.displayname,
        "author_followers": tweet.user.followersCount,
        "author_verified": tweet.user.verified,
        "author_bio": tweet.user.rawDescription,
        "text": tweet.rawContent,
        "created_at": str(tweet.date),
        "url": tweet.url,
        "likes": tweet.likeCount,
        "retweets": tweet.retweetCount,
        "replies_count": tweet.replyCount,
        "views": tweet.viewCount,
        "bookmarks": tweet.bookmarkedCount,
        "image_paths": image_paths,
        "replies": replies,
        "parent_tweet": parent_tweet,
        "quoted_tweet": quoted_tweet,
        "source_account": source_account,
        "discovery_query": discovery_query,
    }


async def scrape_account(api: API, client: httpx.AsyncClient, handle: str) -> list[dict]:
    print(f"Scraping @{handle}...")
    user = await resolve_user(api, handle)
    if user is None:
        print(f"Skipping @{handle}: account not found")
        return []

    posts: list[dict] = []
    async for tweet in api.user_media(user.id, limit=30):
        record = await build_post_record(api, client, tweet, source_account=handle)
        if record:
            posts.append(record)

    print(f"Finished @{handle}: {len(posts)} posts with chart images")
    return posts


async def scrape_search_term(api: API, client: httpx.AsyncClient, term: str) -> list[dict]:
    print(f"Searching X for {term!r}...")
    posts: list[dict] = []
    query = f'"{term}" filter:media min_faves:{MIN_LIKES}'

    async for tweet in api.search(query, limit=SEARCH_LIMIT):
        source_account = getattr(getattr(tweet, "user", None), "username", "") or "search"
        record = await build_post_record(
            api,
            client,
            tweet,
            source_account=source_account,
            discovery_query=term,
        )
        if record:
            posts.append(record)

    print(f"Finished search {term!r}: {len(posts)} posts with chart images")
    return posts


async def main() -> None:
    BASE_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    api = API(str(DB_PATH))
    handles = get_target_accounts()
    search_terms = get_search_terms()
    existing_map = load_existing_posts()
    all_posts: list[dict] = []
    processed_accounts = 0
    processed_search_terms = 0

    async with httpx.AsyncClient(headers={"User-Agent": "macro-dashboard-x-intel/1.0"}) as client:
        for handle in handles:
            normalized_handle = handle.strip().lstrip("@")
            if not normalized_handle:
                continue

            try:
                posts = await scrape_account(api, client, normalized_handle)
                all_posts.extend(posts)
                processed_accounts += 1
            except Exception as exc:
                print(f"Failed to scrape @{normalized_handle}: {exc}")

            await asyncio.sleep(2)

        for term in search_terms:
            normalized_term = term.strip()
            if not normalized_term:
                continue

            try:
                posts = await scrape_search_term(api, client, normalized_term)
                all_posts.extend(posts)
                processed_search_terms += 1
            except Exception as exc:
                print(f"Failed to search term {normalized_term!r}: {exc}")

            await asyncio.sleep(2)

    merged_posts = merge_posts(existing_map, all_posts)
    POSTS_PATH.write_text(json.dumps(merged_posts, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        f"{len(merged_posts)} posts scraped with images from "
        f"{processed_accounts} accounts and {processed_search_terms} search terms"
    )


if __name__ == "__main__":
    asyncio.run(main())
