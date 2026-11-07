"""Collect public Play Store, App Store, and YouTube comments.

Stores comment text only. Usernames, profile links, and channel names are
never written. Run from anywhere:

    python 1_collect.py
"""

import argparse
import hashlib
import re
import time
from datetime import datetime

import pandas as pd
import requests
from google_play_scraper import Sort
from google_play_scraper import reviews as play_reviews

import config

EMAIL_RE = re.compile(r"\b[\w.+-]{1,64}@[\w.-]{2,}\b", re.I)
URL_RE = re.compile(r"https?://\S+|www\.\S+", re.I)
HANDLE_RE = re.compile(r"(?<!\w)@[\w.]{2,}")
PHONE_RE = re.compile(
    r"(?:(?:\+91|91|0)[\s-]?)?[6-9]\d{9}\b|\+\d[\d\-\s]{8,}\d"
)


def strip_pii(text):
    text = "" if text is None else str(text)
    text = URL_RE.sub(" ", text)
    text = EMAIL_RE.sub(" ", text)
    text = HANDLE_RE.sub(" ", text)
    text = PHONE_RE.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def make_id(source, app, text, date):
    raw = f"{source}|{app}|{date}|{text}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:16]


def empty_raw():
    return pd.DataFrame(columns=config.RAW_COLUMNS)


def load_raw():
    df = config.read_csv(config.RAW_CSV)
    if df.empty:
        return empty_raw()
    for col in config.RAW_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    return df[config.RAW_COLUMNS]


def save_raw(df):
    df = df.drop_duplicates(subset=["id"]).reset_index(drop=True)
    config.write_csv(df[config.RAW_COLUMNS], config.RAW_CSV)
    return df


def add_rows(existing, rows):
    if not rows:
        return existing
    fresh = pd.DataFrame(rows)
    for col in config.RAW_COLUMNS:
        if col not in fresh.columns:
            fresh[col] = ""
    combined = pd.concat([existing, fresh[config.RAW_COLUMNS]], ignore_index=True)
    return save_raw(combined)


def row(source, app, text, rating, date, video_id="", context=""):
    text = strip_pii(text)
    if not text:
        return None
    date = "" if date is None else str(date)[:10]
    return {
        "id": make_id(source, app, text, date),
        "source": source,
        "app": app,
        "text": text,
        "rating": "" if rating is None else str(rating),
        "date": date,
        "video_id": video_id or "",
        "context": strip_pii(context)[:500],
    }


def collect_play(existing, groww_limit, competitor_limit):
    print("\nPlay Store")
    for spec in config.PLAY_APPS:
        target = groww_limit if spec["app"] == "Groww" else competitor_limit
        have = existing[(existing["source"] == "play_store") & (existing["app"] == spec["app"])]
        if len(have) >= target:
            print(f"  {spec['app']}: already have {len(have)}, skipping")
            continue
        needed = target - len(have)
        collected = 0
        for lang in ("en", "hi"):
            if collected >= needed:
                break
            token = None
            stale_pages = 0
            while collected < needed:
                try:
                    result, token = play_reviews(
                        spec["package"],
                        lang=lang,
                        country="in",
                        sort=Sort.NEWEST,
                        count=200,
                        continuation_token=token,
                    )
                except Exception as exc:
                    print(f"  {spec['app']} {lang}: stopped ({type(exc).__name__})", flush=True)
                    break
                rows = []
                for review in result:
                    # userName and userImage are intentionally unused.
                    item = row(
                        "play_store",
                        spec["app"],
                        review.get("content"),
                        review.get("score"),
                        review.get("at"),
                        context=spec["app"],
                    )
                    if item:
                        rows.append(item)
                before = len(existing)
                existing = add_rows(existing, rows)
                added = len(existing) - before
                collected += added
                print(
                    f"  {spec['app']} {lang}: page {len(result)}, new {added}, progress {collected}/{needed}",
                    flush=True,
                )
                if not result or token is None or getattr(token, "token", None) is None:
                    break
                if added == 0:
                    stale_pages += 1
                    if stale_pages >= 80:
                        print(f"  {spec['app']} {lang}: feed is repeating, moving on", flush=True)
                        break
                else:
                    stale_pages = 0
                time.sleep(0.45)
        print(f"  {spec['app']}: {collected} new rows", flush=True)
    return existing


def _review_entries(payload):
    feed = payload.get("feed", {})
    entry = feed.get("entry", [])
    if isinstance(entry, dict):
        entry = [entry]
    reviews = []
    for item in entry:
        if not isinstance(item, dict):
            continue
        rating = item.get("im:rating", {})
        if not isinstance(rating, dict) or "label" not in rating:
            continue
        content = item.get("content", {})
        title = item.get("title", {})
        updated = item.get("updated", {})
        body = content.get("label", "") if isinstance(content, dict) else ""
        heading = title.get("label", "") if isinstance(title, dict) else ""
        text = f"{heading}. {body}".strip(" .") if heading and heading not in body else body
        date = updated.get("label", "") if isinstance(updated, dict) else ""
        reviews.append((text, rating.get("label", ""), date))
    return reviews


def collect_app_store(existing, pages):
    print("\nApp Store")
    session = requests.Session()
    session.headers["User-Agent"] = "DiscoveryEngine/1.0 (public review research)"
    for spec in config.PLAY_APPS:
        got = 0
        for page in range(1, pages + 1):
            url = (
                "https://itunes.apple.com/in/rss/customerreviews/"
                f"page={page}/id={spec['apple_id']}/sortby=mostrecent/json"
            )
            try:
                response = session.get(url, timeout=30)
            except requests.RequestException as exc:
                print(f"  {spec['app']} page {page}: {type(exc).__name__}")
                break
            if response.status_code != 200:
                break
            try:
                payload = response.json()
            except ValueError:
                break
            reviews = _review_entries(payload)
            if not reviews:
                break
            rows = []
            for text, rating, date in reviews:
                # author.name is intentionally unused.
                item = row(
                    "app_store",
                    spec["app"],
                    text,
                    rating,
                    date,
                    context=spec["app"],
                )
                if item:
                    rows.append(item)
            before = len(existing)
            existing = add_rows(existing, rows)
            added = len(existing) - before
            got += added
            print(f"  {spec['app']} page {page}: {len(reviews)} reviews, {added} new")
            if got >= 500:
                break
            time.sleep(0.4)
        print(f"  {spec['app']}: {got} new App Store rows")
    return existing


def collect_youtube(existing, comment_limit):
    print("\nYouTube")
    if not config.YOUTUBE_API_KEY:
        print("  No YouTube key loaded. Skipping YouTube.")
        return existing
    have = len(existing[existing["source"] == "youtube"])
    if have >= comment_limit:
        print(f"  Already have {have} YouTube rows, skipping")
        return existing

    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError

    youtube = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY, cache_discovery=False)
    videos = {}
    for video_id in config.YOUTUBE_VIDEO_IDS:
        videos[video_id] = {"title": "", "description": ""}

    for query in config.YOUTUBE_QUERIES:
        try:
            found = youtube.search().list(
                part="snippet",
                q=query,
                type="video",
                maxResults=8,
                regionCode="IN",
                relevanceLanguage="hi",
                safeSearch="moderate",
            ).execute()
        except HttpError as exc:
            print(f"  Search stopped ({exc.resp.status if exc.resp else 'error'})")
            break
        for item in found.get("items", []):
            video_id = item.get("id", {}).get("videoId")
            snippet = item.get("snippet", {})
            if video_id and video_id not in videos:
                videos[video_id] = {
                    "title": snippet.get("title", ""),
                    "description": "",
                }
        time.sleep(0.3)
        if len(videos) >= 45:
            break

    ids = list(videos.keys())
    for start in range(0, len(ids), 50):
        chunk = ids[start : start + 50]
        try:
            details = youtube.videos().list(part="snippet", id=",".join(chunk)).execute()
        except HttpError as exc:
            print(f"  Video details stopped ({exc.resp.status if exc.resp else 'error'})")
            break
        for item in details.get("items", []):
            snippet = item.get("snippet", {})
            # channelTitle is intentionally unused.
            videos[item["id"]]["title"] = snippet.get("title", "")
            videos[item["id"]]["description"] = snippet.get("description", "")

    video_rows = []
    for video_id, meta in videos.items():
        video_rows.append(
            {
                "video_id": video_id,
                "title": meta.get("title", ""),
                "description": (meta.get("description") or "")[:500],
            }
        )
    if video_rows:
        config.write_csv(pd.DataFrame(video_rows), config.VIDEOS_CSV)
    print(f"  Videos selected: {len(videos)}")

    remaining = comment_limit - have
    per_video = 400
    already = set(existing.loc[existing["source"] == "youtube", "video_id"].astype(str))
    for video_id, meta in videos.items():
        if video_id in already:
            continue
        if remaining <= 0:
            break
        title = meta.get("title") or ""
        description = (meta.get("description") or "")[:400]
        context = f"{title}\n{description}".strip()
        page_token = None
        video_got = 0
        while video_got < per_video and remaining > 0:
            try:
                response = youtube.commentThreads().list(
                    part="snippet",
                    videoId=video_id,
                    maxResults=min(100, per_video - video_got),
                    order="relevance",
                    textFormat="plainText",
                    pageToken=page_token,
                ).execute()
            except HttpError as exc:
                status = exc.resp.status if exc.resp else 0
                if status in (403, 404):
                    print(f"  {video_id}: comments unavailable")
                else:
                    print(f"  {video_id}: stopped ({status})")
                break
            rows = []
            for item in response.get("items", []):
                snippet = item.get("snippet", {}).get("topLevelComment", {}).get("snippet", {})
                # authorDisplayName and authorChannelUrl are intentionally unused.
                item_row = row(
                    "youtube",
                    "",
                    snippet.get("textOriginal") or snippet.get("textDisplay"),
                    "",
                    snippet.get("publishedAt", ""),
                    video_id=video_id,
                    context=context,
                )
                if item_row:
                    rows.append(item_row)
            before = len(existing)
            existing = add_rows(existing, rows)
            added = len(existing) - before
            video_got += len(response.get("items", []))
            remaining -= added
            page_token = response.get("nextPageToken")
            if not page_token or not response.get("items"):
                break
            time.sleep(0.25)
        print(f"  {video_id}: kept up to {video_got} comments ({title[:60]})")
    return existing


def collect_manual(existing):
    path = config.DATA_DIR / "manual_forums.csv"
    manual = config.read_csv(path)
    if manual.empty or "text" not in manual.columns:
        print("\nManual file: none")
        return existing
    rows = []
    for _, item in manual.iterrows():
        label = str(item.get("source_label", "")).strip()
        made = row(
            "manual",
            label,
            item.get("text"),
            "",
            item.get("date", ""),
            context=label,
        )
        if made:
            rows.append(made)
    before = len(existing)
    existing = add_rows(existing, rows)
    print(f"\nManual file: {len(existing) - before} new rows")
    return existing


def summarize(df):
    print(f"\nRaw rows: {len(df)}")
    if df.empty:
        return
    by_source = df.groupby("source").size().to_dict()
    by_app = df.groupby(["source", "app"]).size().to_dict()
    printable = {f"{source}|{app}": int(count) for (source, app), count in by_app.items()}
    print("By source:", {key: int(value) for key, value in by_source.items()})
    config.update_funnel(
        raw_total=int(len(df)),
        raw_by_source={key: int(value) for key, value in by_source.items()},
        raw_by_source_app=printable,
        collected_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )
    print("\n5 sample rows:")
    config.print_samples(df)


def main():
    parser = argparse.ArgumentParser(description="Collect public SIP comments")
    parser.add_argument("--groww-limit", type=int, default=20000)
    parser.add_argument("--competitor-limit", type=int, default=5000)
    parser.add_argument("--app-store-pages", type=int, default=10)
    parser.add_argument("--youtube-limit", type=int, default=20000)
    parser.add_argument("--skip-play", action="store_true")
    parser.add_argument("--skip-app-store", action="store_true")
    parser.add_argument("--skip-youtube", action="store_true")
    args = parser.parse_args()

    config.ensure_data_dir()
    existing = load_raw()
    print(f"Existing raw rows: {len(existing)}")
    if not args.skip_play:
        existing = collect_play(existing, args.groww_limit, args.competitor_limit)
    if not args.skip_app_store:
        existing = collect_app_store(existing, args.app_store_pages)
    if not args.skip_youtube:
        existing = collect_youtube(existing, args.youtube_limit)
    existing = collect_manual(existing)
    summarize(existing)


if __name__ == "__main__":
    main()
