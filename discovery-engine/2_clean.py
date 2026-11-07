"""Hygiene and the SIP keyword gate. No model calls.

    python 2_clean.py
"""

import hashlib
import importlib.util
import re

import config


def _load_collect():
    spec = importlib.util.spec_from_file_location("collect_mod", config.ROOT / "1_collect.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


collect = _load_collect()

SPAM_RE = re.compile(
    r"\b(telegram|t\.me|whatsapp me|dm me|join my group|join my telegram|"
    r"earn daily|guaranteed returns?|double your money)\b",
    re.I,
)
LETTER_RE = re.compile(r"[A-Za-z\u0900-\u097F]")


def normalize(text):
    text = str(text).lower()
    text = re.sub(r"[^a-z0-9\u0900-\u097f\s]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def simhash(text):
    words = normalize(text).split()
    if not words:
        return 0
    acc = [0] * 64
    for word in words:
        digest = int(hashlib.md5(word.encode("utf-8")).hexdigest()[:16], 16)
        for bit in range(64):
            acc[bit] += 1 if (digest >> bit) & 1 else -1
    value = 0
    for bit, score in enumerate(acc):
        if score >= 0:
            value |= 1 << bit
    return value


def hamming(left, right):
    return bin(left ^ right).count("1")


def drop_near_duplicates(df):
    """Drop comments with a very similar word fingerprint already kept."""
    buckets = {}
    keep_index = []
    for idx, text in df["text"].items():
        fingerprint = simhash(text)
        key = fingerprint >> 48
        previous = buckets.get(key, [])
        if any(hamming(fingerprint, old) <= 3 for old in previous):
            continue
        previous.append(fingerprint)
        buckets[key] = previous
        keep_index.append(idx)
    return df.loc[keep_index].copy()


def main():
    config.ensure_data_dir()
    raw = config.read_csv(config.RAW_CSV)
    print(f"Start: {len(raw)} raw rows")
    if raw.empty:
        print("No raw.csv yet. Run 1_collect.py first.")
        return

    df = raw.copy()
    for col in config.RAW_COLUMNS:
        if col not in df.columns:
            df[col] = ""
    df["text"] = df["text"].map(collect.strip_pii)
    df = df[df["text"].str.len() > 0]
    print(f"After stripping contact details: {len(df)}")

    word_count = df["text"].str.split().str.len()
    long_enough = (word_count >= 5) & (df["text"].str.len() >= 25)
    df = df[long_enough]
    print(f"After dropping short text: {len(df)}")

    has_words = df["text"].map(lambda text: bool(LETTER_RE.search(str(text))))
    df = df[has_words]
    print(f"After dropping emoji-only text: {len(df)}")

    spam = df["text"].map(lambda text: bool(SPAM_RE.search(str(text))))
    print(f"Spam rows removed: {int(spam.sum())}")
    df = df[~spam]
    print(f"After spam filter: {len(df)}")

    before_exact = len(df)
    df = df.copy()
    df["norm"] = df["text"].map(normalize)
    df = df.drop_duplicates(subset=["norm"])
    print(f"After exact duplicates: {len(df)} (removed {before_exact - len(df)})")

    before_near = len(df)
    df = drop_near_duplicates(df)
    print(f"After near-duplicates: {len(df)} (removed {before_near - len(df)})")

    hygiene = df.drop(columns=["norm"]).copy()
    hygiene["keyword_count"] = hygiene["text"].map(lambda text: config.keyword_count(text, config.KEYWORDS))
    matched = hygiene[hygiene["keyword_count"] > 0].sort_values(
        ["keyword_count", "date"], ascending=[False, False]
    )
    unmatched = hygiene[hygiene["keyword_count"] == 0]
    print(f"Keyword matches: {len(matched)}")
    print(f"No keyword: {len(unmatched)}")

    if len(unmatched):
        sample = unmatched.sample(n=min(30, len(unmatched)), random_state=11)
        config.write_csv(sample[config.RAW_COLUMNS + ["keyword_count"]], config.DISCARD_KEYWORD_CSV)
        print(f"Wrote {len(sample)} discarded rows to {config.DISCARD_KEYWORD_CSV.name} for a spot check")

    capped = matched.head(config.KEYWORD_CAP).copy()
    print(f"After keyword cap ({config.KEYWORD_CAP}): {len(capped)}")

    # Next tier, used only if the relevance step cannot reach 1,500 comments.
    loose_pool = unmatched.copy()
    loose_pool["keyword_count"] = loose_pool["text"].map(
        lambda text: config.keyword_count(text, config.LOOSE_KEYWORDS)
    )
    loose = loose_pool[loose_pool["keyword_count"] > 0].sort_values(
        "keyword_count", ascending=False
    ).head(2000)
    config.write_csv(loose.drop(columns=[], errors="ignore"), config.LOOSE_CSV)
    print(f"Loose reserve (not in the working set yet): {len(loose)}")

    keep_cols = config.RAW_COLUMNS + ["keyword_count"]
    config.write_csv(capped[keep_cols], config.CLEAN_CSV)
    config.update_funnel(
        after_hygiene=int(len(hygiene)),
        after_keyword_match=int(len(matched)),
        after_keyword_cap=int(len(capped)),
        loose_reserve=int(len(loose)),
    )
    print("\n5 sample rows from clean.csv:")
    config.print_samples(capped)


if __name__ == "__main__":
    main()
