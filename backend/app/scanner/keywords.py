# Bahasa Indonesia gambling keyword lists - authoritative source for all scan modules
#
# Inclusion rule: only terms that are EXCLUSIVE to Indonesian online gambling slang.
# Words that appear in legitimate government/news content (judi online, casino online,
# togel, judi bola) are intentionally excluded - they generate false positives on
# government articles reporting on gambling dangers and waste Serper API credits.

GAMBLING_KEYWORDS: list[str] = [
    # Slot injection slang - these never appear in legitimate .go.id content
    "slot gacor",
    "bocoran slot",
    "rtp slot",
    "gacor hari ini",
    "slot hari ini",
    "maxwin",
    "scatter hitam",
    "pola slot",
    # Gambling brand/site codes injected as SEO
    "slot138",
    "slot777",
    "slot303",
    "joker123",
    "sbobet",
    "pragmatic play",
    "pg soft",
    "mahjong ways",
    "sweet bonanza",
    # Togel-specific codes (not the word togel alone)
    "bocoran togel",
    "prediksi togel",
    "result sgp",
    "result hk",
    "keluaran sgp",
    "keluaran hk",
    # Transaction codes used in injection CTAs
    "deposit pulsa",
    "withdraw cepat",
    "bonus deposit",
]

# Anchor text patterns for injected link detection
INJECTED_ANCHOR_PATTERNS: list[str] = [
    "slot gacor",
    "bocoran slot",
    "rtp slot",
    "maxwin",
    "joker123",
    "sbobet",
    "pragmatic play",
    "mahjong ways",
]

# Serper dork queries - KEEP THIS LIST SHORT.
# Each entry = 1 Serper API credit per domain scanned.
# TLD sweep (50 child scans) x N queries = N*50 credits per sweep.
# Only use phrases that ONLY appear on injected pages, never in legit gov content.
DORK_QUERIES: list[str] = [
    '"slot gacor"',   # highest signal - every real injection in test data matched this
    # '"bocoran slot"', # secondary coverage - uncomment if credits allow
    # '"situs slot"', # tertiary - least unique hits, disable to save credits
]

# Known gambling redirect domain patterns
GAMBLING_DOMAIN_PATTERNS: list[str] = [
    r"slot\d+",
    r"judi\w+",
    r"togel\w+",
    r"casino\w+",
    r"poker\w+",
    r"sbobet",
    r"idn\w+",
    r"gacor",
]
