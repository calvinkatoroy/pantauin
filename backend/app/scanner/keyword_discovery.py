"""
Module: keyword_discovery
Extracts candidate gambling keywords from confirmed injected pages.
Runs after page_crawl confirms a finding - mines the injected content
for new terminology not yet in the keyword list.

The feedback loop:
    confirmed injection → extract candidates → store in DB
    → auto-approve if seen on 3+ sites → next scan uses new keywords
    → finds more sites → discovers more keywords
"""
import json
import logging
import re
import string
from collections import Counter
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.scan import DiscoveredKeyword
from app.scanner.keywords import GAMBLING_KEYWORDS, INJECTED_ANCHOR_PATTERNS

logger = logging.getLogger(__name__)

# Auto-approve threshold - seen on this many distinct sites = trusted
# Set conservatively: government news articles about gambling are common on .go.id,
# so a word must appear on many independently compromised sites before trusting it.
AUTO_APPROVE_THRESHOLD = 5

# Minimum character length for a candidate keyword
MIN_KEYWORD_LEN = 4

# Maximum words in a candidate n-gram phrase
MAX_NGRAM_WORDS = 4

# Indonesian stopwords to filter out.
# Includes generic government/news vocabulary that co-occurs with "judi" in
# legitimate government articles about gambling dangers - NOT injection markers.
INDONESIAN_STOPWORDS = {
    # Core function words
    "yang", "dan", "di", "ke", "dari", "untuk", "dengan", "pada", "adalah",
    "ini", "itu", "ada", "tidak", "juga", "dalam", "atau", "sudah", "akan",
    "bisa", "kami", "kita", "mereka", "anda", "saya", "dia", "ber", "ter",
    "me", "se", "per", "pem", "peng", "pen", "mem", "men", "meng",
    "nya", "lah", "kah", "pun", "hal", "cara", "info", "lebih",
    "oleh", "karena", "saat", "setelah", "sebelum", "ketika", "jika",
    "maka", "agar", "namun", "tetapi", "tapi", "serta", "bahwa",
    "telah", "sedang", "masih", "hanya", "semua", "setiap", "banyak",
    "sangat", "cukup", "sama", "lain", "baru", "lama",
    # Common web/HTML terms to ignore
    "http", "https", "www", "com", "html", "php", "asp", "css", "js",
    "home", "page", "menu", "link", "klik", "click", "here", "more",
    "read", "baca", "lihat", "view", "next", "prev", "back",
    # Generic government/news vocabulary - these appear in ARTICLES ABOUT gambling,
    # not in injected gambling content. Including them here prevents false discovery
    # when the discovery system runs on a legitimate government page caught by a
    # broad dork query.
    "beranda", "berita", "menjadi", "masyarakat", "anak", "agama", "dampak",
    "tersebut", "situs", "media", "internet", "artikel", "data", "pemerintah",
    "indonesia", "informasi", "digital", "nasional", "sosial", "moral",
    "edukasi", "upaya", "keluarga", "individu", "ekonomi", "kasus",
    "bahaya", "dampak", "larangan", "pencegahan", "penanganan",
    "modus", "sebagai", "secara", "bagi", "luar", "aktif", "kolom",
    "orang", "tahun", "bulan", "jumat", "senin", "selasa", "rabu", "kamis",
}

# Patterns that strongly signal gambling context - used to validate candidates
GAMBLING_CONTEXT_SIGNALS = [
    r'\b(slot|judi|togel|casino|poker|taruhan|bet|win|menang|bonus|deposit)\b',
    r'\b(gacor|maxwin|jackpot|scatter|wild|spin|rtp)\b',
    r'\b(\d{2,4}d|sgp|hk|sdy|sydney)\b',
    r'\b(sbobet|idn|pragmatic|pgsoft|habanero)\b',
]
CONTEXT_RE = re.compile("|".join(GAMBLING_CONTEXT_SIGNALS), re.IGNORECASE)


def _tokenize(text: str) -> list[str]:
    """Clean and tokenize page text into words."""
    text = text.lower()
    # Remove URLs
    text = re.sub(r'https?://\S+', ' ', text)
    # Remove HTML entities
    text = re.sub(r'&\w+;', ' ', text)
    # Keep only alphanumeric + spaces
    text = re.sub(r'[^\w\s]', ' ', text)
    tokens = text.split()
    return [t for t in tokens if len(t) >= MIN_KEYWORD_LEN and t not in INDONESIAN_STOPWORDS]


def _extract_ngrams(tokens: list[str], n: int) -> list[str]:
    return [" ".join(tokens[i:i+n]) for i in range(len(tokens) - n + 1)]


def _score_candidate(candidate: str, full_text: str) -> float:
    """
    Score a candidate keyword 0.0–1.0 based on gambling context signals.
    Higher score = more likely to be a gambling term.
    """
    score = 0.0

    # Direct gambling context in surrounding text
    if CONTEXT_RE.search(candidate):
        score += 0.5

    # Candidate appears near known gambling keywords
    for kw in GAMBLING_KEYWORDS[:20]:  # check against core keywords only
        pattern = re.compile(
            rf'.{{0,50}}{re.escape(candidate)}.{{0,50}}',
            re.IGNORECASE | re.DOTALL
        )
        for match in pattern.finditer(full_text):
            if kw.lower() in match.group(0).lower():
                score += 0.3
                break

    # Looks like a brand name / product name (TitleCase or ALL_CAPS mixed with numbers)
    if re.match(r'^[A-Z][a-z]+\d*$', candidate.title().replace(" ", "")):
        score += 0.1

    # Contains numbers typical of gambling (138, 777, 303, 4d etc.)
    if re.search(r'\d{2,4}', candidate):
        score += 0.2

    return min(score, 1.0)


def extract_candidates(page_text: str, known_keywords: list[str]) -> list[tuple[str, float]]:
    """
    Extract candidate new keywords from confirmed injected page text.
    Returns list of (keyword, confidence_score) not already in known list.
    """
    known_lower = {kw.lower() for kw in known_keywords}
    tokens = _tokenize(page_text)

    if not tokens:
        return []

    # Count frequency of all n-grams (1 to MAX_NGRAM_WORDS)
    candidates: Counter = Counter()
    for n in range(1, MAX_NGRAM_WORDS + 1):
        for gram in _extract_ngrams(tokens, n):
            if gram not in known_lower and gram not in INDONESIAN_STOPWORDS:
                candidates[gram] += 1

    # Filter: must appear at least twice and have gambling context signal
    results = []
    for candidate, freq in candidates.most_common(100):
        if freq < 2:
            break
        if len(candidate) < MIN_KEYWORD_LEN:
            continue
        # Candidate itself must contain a gambling signal - checking only the page
        # would pass every word on any government news article that mentions gambling.
        if not CONTEXT_RE.search(candidate):
            continue

        score = _score_candidate(candidate, page_text)
        if score >= 0.3:
            results.append((candidate, round(score, 2)))

    # Sort by score desc, limit to top 20 candidates per page
    results.sort(key=lambda x: x[1], reverse=True)
    return results[:20]


async def process_finding(
    db: AsyncSession,
    page_text: str,
    source_url: str,
    known_keywords: list[str],
) -> list[str]:
    """
    Extract candidates from a confirmed finding and upsert into DB.
    Returns list of newly discovered keyword strings.
    """
    candidates = extract_candidates(page_text, known_keywords)
    newly_added = []

    for keyword, confidence in candidates:
        # Check if already exists
        result = await db.execute(
            select(DiscoveredKeyword).where(DiscoveredKeyword.keyword == keyword)
        )
        existing = result.scalar_one_or_none()

        if existing:
            # Increment frequency, update source_urls
            existing.frequency += 1
            existing.confidence = max(existing.confidence, confidence)

            # Add source URL to list
            urls = json.loads(existing.source_urls or "[]")
            if source_url not in urls:
                urls.append(source_url)
                existing.source_urls = json.dumps(urls[:20])  # cap at 20 sources

            # Auto-approve if threshold reached
            if existing.frequency >= AUTO_APPROVE_THRESHOLD and existing.status == "pending":
                existing.status = "approved"
                existing.approved_at = datetime.now(timezone.utc)
                logger.info("Auto-approved keyword: '%s' (seen on %d sites)", keyword, existing.frequency)

        else:
            # New discovery
            new_kw = DiscoveredKeyword(
                keyword=keyword,
                frequency=1,
                confidence=confidence,
                status="pending",
                source_urls=json.dumps([source_url]),
                is_seed=False,
            )
            db.add(new_kw)
            newly_added.append(keyword)
            logger.info("New keyword candidate discovered: '%s' (confidence: %.2f)", keyword, confidence)

    await db.commit()
    return newly_added


async def get_active_keywords(db: AsyncSession) -> list[str]:
    """
    Return all active keywords - seed list + approved discoveries.
    This is what page_crawl uses at scan time.
    """
    result = await db.execute(
        select(DiscoveredKeyword.keyword).where(
            DiscoveredKeyword.status.in_(["approved", "seed"])
        )
    )
    db_keywords = [row[0] for row in result.fetchall()]

    # Merge with static seed list (deduped)
    all_keywords = list({kw.lower() for kw in GAMBLING_KEYWORDS + db_keywords})
    return all_keywords


async def seed_keywords(db: AsyncSession) -> None:
    """
    Seed the discovered_keywords table with the static keyword list on first run.
    Idempotent - skips existing entries.
    """
    for kw in GAMBLING_KEYWORDS:
        result = await db.execute(
            select(DiscoveredKeyword).where(DiscoveredKeyword.keyword == kw.lower())
        )
        if not result.scalar_one_or_none():
            db.add(DiscoveredKeyword(
                keyword=kw.lower(),
                frequency=0,
                confidence=1.0,
                status="approved",
                is_seed=True,
                approved_at=datetime.now(timezone.utc),
            ))
    await db.commit()
