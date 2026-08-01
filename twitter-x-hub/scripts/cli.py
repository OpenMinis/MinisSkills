"""Command-line interface for twitter-x-hub.

Adapted from https://github.com/public-clis/twitter-cli (v0.8.6)
Auth is provided via --auth-token / --ct0 flags or
TWITTER_AUTH_TOKEN / TWITTER_CT0 environment variables.

Usage:
    python -m scripts.cli <subcommand> [options]
"""

from __future__ import annotations

import argparse
import dataclasses
import json
import os
import sys
from typing import Any, List

from .client import TwitterAPIError, TwitterClient
from .models import BookmarkFolder, Tweet, UserProfile


# ── Auth helpers ─────────────────────────────────────────────────────────

def _get_client(args: argparse.Namespace) -> TwitterClient:
    auth_token = getattr(args, "auth_token", None) or os.environ.get("TWITTER_AUTH_TOKEN", "")
    ct0 = getattr(args, "ct0", None) or os.environ.get("TWITTER_CT0", "")
    if not auth_token or not ct0:
        print(
            "Error: auth_token and ct0 are required.\n"
            "  Option 1: --auth-token <value> --ct0 <value>\n"
            "  Option 2: set TWITTER_AUTH_TOKEN and TWITTER_CT0 environment variables",
            file=sys.stderr,
        )
        sys.exit(1)
    return TwitterClient(auth_token=auth_token, ct0=ct0)


def _add_auth_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--auth-token", metavar="TOKEN",
                   help="Twitter auth_token cookie (or set TWITTER_AUTH_TOKEN)")
    p.add_argument("--ct0", metavar="CT0",
                   help="Twitter ct0 cookie (or set TWITTER_CT0)")


# ── Output helpers ────────────────────────────────────────────────────────

def _to_dict(obj: Any) -> Any:
    if dataclasses.is_dataclass(obj) and not isinstance(obj, type):
        return {k: _to_dict(v) for k, v in dataclasses.asdict(obj).items()}
    if isinstance(obj, list):
        return [_to_dict(i) for i in obj]
    return obj


def _print_json(data: Any) -> None:
    print(json.dumps(_to_dict(data), ensure_ascii=False, indent=2))


def _print_tweets(tweets: List[Tweet], as_json: bool) -> None:
    if as_json:
        _print_json(tweets)
        return
    for t in tweets:
        rt_tag = f"  [RT by @{t.retweeted_by}]" if t.is_retweet else ""
        sub_tag = " [subscriber only]" if t.is_subscriber_only else ""
        print(f"── @{t.author.screen_name}{rt_tag}{sub_tag}  [{t.created_at}]")
        print(f"   {t.text[:280]}")
        m = t.metrics
        print(f"   ❤️ {m.likes}  🔁 {m.retweets}  💬 {m.replies}  👁 {m.views}  🔖 {m.bookmarks}")
        if t.quoted_tweet:
            q = t.quoted_tweet
            print(f"   ↳ QT @{q.author.screen_name}: {q.text[:120]}")
        if t.article_title:
            print(f"   📄 Article: {t.article_title}")
        if t.media:
            print(f"   📎 {len(t.media)} media item(s)")
        print()


def _print_users(users: List[UserProfile], as_json: bool) -> None:
    if as_json:
        _print_json(users)
        return
    for u in users:
        verified = " ✓" if u.verified else ""
        print(f"@{u.screen_name}{verified}  ({u.name})")
        print(f"  followers={u.followers_count}  following={u.following_count}  tweets={u.tweets_count}")
        if u.bio:
            print(f"  {u.bio[:120]}")
        print()


# ── Subcommand handlers ───────────────────────────────────────────────────

def cmd_feed(args: argparse.Namespace) -> None:
    client = _get_client(args)
    if args.type == "following":
        tweets = client.fetch_following_feed(count=args.max)
    else:
        tweets = client.fetch_home_timeline(count=args.max)
    _print_tweets(tweets, args.json)


def cmd_bookmarks(args: argparse.Namespace) -> None:
    client = _get_client(args)
    tweets = client.fetch_bookmarks(count=args.max)
    _print_tweets(tweets, args.json)


def cmd_bookmark_folders(args: argparse.Namespace) -> None:
    client = _get_client(args)
    folders = client.fetch_bookmark_folders()
    if args.json:
        _print_json(folders)
    else:
        for f in folders:
            print(f"[{f.id}] {f.name}")


def cmd_search(args: argparse.Namespace) -> None:
    client = _get_client(args)
    tweets = client.fetch_search(args.query, count=args.max, product=args.tab)
    _print_tweets(tweets, args.json)


def cmd_user(args: argparse.Namespace) -> None:
    client = _get_client(args)
    user = client.fetch_user(args.screen_name)
    if args.json:
        _print_json(user)
    else:
        verified = " ✓" if user.verified else ""
        print(f"@{user.screen_name}{verified}  ({user.name})")
        print(f"  id={user.id}")
        print(f"  followers={user.followers_count}  following={user.following_count}  tweets={user.tweets_count}")
        if user.bio:
            print(f"  bio: {user.bio}")
        if user.location:
            print(f"  location: {user.location}")
        print(f"  joined: {user.created_at}")


def cmd_user_posts(args: argparse.Namespace) -> None:
    client = _get_client(args)
    user = client.fetch_user(args.screen_name)
    tweets = client.fetch_user_tweets(user.id, count=args.max)
    _print_tweets(tweets, args.json)


def cmd_user_likes(args: argparse.Namespace) -> None:
    client = _get_client(args)
    user = client.fetch_user(args.screen_name)
    tweets = client.fetch_user_likes(user.id, count=args.max)
    _print_tweets(tweets, args.json)


def cmd_tweet(args: argparse.Namespace) -> None:
    client = _get_client(args)
    # Accept full URL or bare ID
    tweet_id = args.tweet_id.rstrip("/").split("/")[-1]
    tweets = client.fetch_tweet_detail(tweet_id, count=args.max)
    _print_tweets(tweets, args.json)


def cmd_tweet_by_id(args: argparse.Namespace) -> None:
    """Fetch a single tweet by ID (TweetResultByRestId — faster than TweetDetail)."""
    client = _get_client(args)
    tweet_id = args.tweet_id.rstrip("/").split("/")[-1]
    tweet = client.fetch_tweet_by_id(tweet_id)
    if tweet is None:
        print(f"Tweet {tweet_id} not found.", file=sys.stderr)
        sys.exit(1)
    _print_tweets([tweet], args.json)


def cmd_list(args: argparse.Namespace) -> None:
    client = _get_client(args)
    tweets = client.fetch_list_timeline(args.list_id, count=args.max)
    _print_tweets(tweets, args.json)


def cmd_followers(args: argparse.Namespace) -> None:
    client = _get_client(args)
    users = client.fetch_followers(args.user_id, count=args.max)
    _print_users(users, args.json)


def cmd_following(args: argparse.Namespace) -> None:
    client = _get_client(args)
    users = client.fetch_following(args.user_id, count=args.max)
    _print_users(users, args.json)


def cmd_post(args: argparse.Namespace) -> None:
    client = _get_client(args)
    result = client.post_tweet(args.text, reply_to_id=getattr(args, "reply_to", None))
    tweet_id = (
        result.get("data", {}).get("create_tweet", {}).get("tweet_results", {})
        .get("result", {}).get("rest_id", "")
    )
    if tweet_id:
        print(f"Posted: https://x.com/i/web/status/{tweet_id}")
    else:
        print("Posted (no ID returned).")


def cmd_delete(args: argparse.Namespace) -> None:
    client = _get_client(args)
    client.delete_tweet(args.tweet_id)
    print(f"Deleted tweet {args.tweet_id}")


def cmd_like(args: argparse.Namespace) -> None:
    client = _get_client(args)
    client.like_tweet(args.tweet_id)
    print(f"Liked {args.tweet_id}")


def cmd_unlike(args: argparse.Namespace) -> None:
    client = _get_client(args)
    client.unlike_tweet(args.tweet_id)
    print(f"Unliked {args.tweet_id}")


def cmd_retweet(args: argparse.Namespace) -> None:
    client = _get_client(args)
    client.retweet(args.tweet_id)
    print(f"Retweeted {args.tweet_id}")


def cmd_unretweet(args: argparse.Namespace) -> None:
    client = _get_client(args)
    client.unretweet(args.tweet_id)
    print(f"Unretweeted {args.tweet_id}")


def cmd_bookmark(args: argparse.Namespace) -> None:
    client = _get_client(args)
    client.bookmark_tweet(args.tweet_id)
    print(f"Bookmarked {args.tweet_id}")


def cmd_unbookmark(args: argparse.Namespace) -> None:
    client = _get_client(args)
    client.unbookmark_tweet(args.tweet_id)
    print(f"Removed bookmark {args.tweet_id}")


# ── Argument parser ───────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="twitter-x-hub",
        description="Twitter/X GraphQL client (cookie auth, zero third-party deps).",
    )
    sub = parser.add_subparsers(dest="command", metavar="<command>")
    sub.required = True

    # feed
    p = sub.add_parser("feed", help="Home timeline (For You or Following)")
    p.add_argument("--type", choices=["for-you", "following"], default="for-you")
    p.add_argument("--max", type=int, default=20, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_feed)

    # bookmarks
    p = sub.add_parser("bookmarks", help="Saved bookmarks")
    p.add_argument("--max", type=int, default=50, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_bookmarks)

    # bookmark-folders
    p = sub.add_parser("bookmark-folders", help="List bookmark folders")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_bookmark_folders)

    # search
    p = sub.add_parser("search", help="Search tweets")
    p.add_argument("query", help="Search query")
    p.add_argument("--tab", choices=["Top", "Latest", "Photos", "Videos"], default="Top")
    p.add_argument("--max", type=int, default=20, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_search)

    # user
    p = sub.add_parser("user", help="User profile")
    p.add_argument("screen_name")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_user)

    # user-posts
    p = sub.add_parser("user-posts", help="Tweets posted by a user")
    p.add_argument("screen_name")
    p.add_argument("--max", type=int, default=20, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_user_posts)

    # user-likes
    p = sub.add_parser("user-likes", help="Tweets liked by a user (own account only)")
    p.add_argument("screen_name")
    p.add_argument("--max", type=int, default=20, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_user_likes)

    # tweet
    p = sub.add_parser("tweet", help="Tweet detail + reply thread")
    p.add_argument("tweet_id", help="Tweet ID or full URL")
    p.add_argument("--max", type=int, default=20, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_tweet)

    # tweet-by-id (new — TweetResultByRestId, faster single-tweet fetch)
    p = sub.add_parser("tweet-by-id", help="Fetch a single tweet by ID (no replies)")
    p.add_argument("tweet_id", help="Tweet ID or full URL")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_tweet_by_id)

    # list
    p = sub.add_parser("list", help="Twitter List timeline")
    p.add_argument("list_id")
    p.add_argument("--max", type=int, default=20, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_list)

    # followers
    p = sub.add_parser("followers", help="Followers of a user (requires user_id)")
    p.add_argument("user_id")
    p.add_argument("--max", type=int, default=20, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_followers)

    # following
    p = sub.add_parser("following", help="Users a user follows (requires user_id)")
    p.add_argument("user_id")
    p.add_argument("--max", type=int, default=20, metavar="N")
    p.add_argument("--json", action="store_true")
    _add_auth_args(p)
    p.set_defaults(func=cmd_following)

    # post
    p = sub.add_parser("post", help="Post a new tweet")
    p.add_argument("text")
    p.add_argument("--reply-to", metavar="TWEET_ID", dest="reply_to")
    _add_auth_args(p)
    p.set_defaults(func=cmd_post)

    # delete
    p = sub.add_parser("delete", help="Delete a tweet")
    p.add_argument("tweet_id")
    _add_auth_args(p)
    p.set_defaults(func=cmd_delete)

    # like / unlike
    for name, fn in [("like", cmd_like), ("unlike", cmd_unlike)]:
        p = sub.add_parser(name, help=f"{'Like' if name == 'like' else 'Unlike'} a tweet")
        p.add_argument("tweet_id")
        _add_auth_args(p)
        p.set_defaults(func=fn)

    # retweet / unretweet
    for name, fn in [("retweet", cmd_retweet), ("unretweet", cmd_unretweet)]:
        p = sub.add_parser(name, help=f"{'Retweet' if name == 'retweet' else 'Undo retweet'}")
        p.add_argument("tweet_id")
        _add_auth_args(p)
        p.set_defaults(func=fn)

    # bookmark / unbookmark
    for name, fn in [("bookmark", cmd_bookmark), ("unbookmark", cmd_unbookmark)]:
        p = sub.add_parser(name, help=f"{'Bookmark' if name == 'bookmark' else 'Remove bookmark'}")
        p.add_argument("tweet_id")
        _add_auth_args(p)
        p.set_defaults(func=fn)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        args.func(args)
    except TwitterAPIError as exc:
        print(f"API Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except RuntimeError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        sys.exit(1)
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
