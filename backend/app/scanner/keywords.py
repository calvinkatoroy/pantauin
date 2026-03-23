# Bahasa Indonesia gambling keyword lists - authoritative source for all scan modules

GAMBLING_KEYWORDS: list[str] = [
    # Core terms
    "judi online",
    "judi bola",
    "judi slot",
    "situs judi",
    "agen judi",
    "bandar judi",
    "daftar judi",
    # Slot terms
    "slot gacor",
    "slot online",
    "slot138",
    "slot777",
    "slot303",
    "bocoran slot",
    "rtp slot",
    "link slot",
    "daftar slot",
    "situs slot",
    "slot hari ini",
    "gacor hari ini",
    "maxwin",
    "jackpot slot",
    # Togel / lottery
    "togel",
    "toto",
    "togel online",
    "prediksi togel",
    "bocoran togel",
    "angka togel",
    "4d",
    "3d togel",
    "sgp",
    "hk",
    "sydney",
    "result sgp",
    "result hk",
    # Poker / casino
    "poker online",
    "idn poker",
    "casino online",
    "live casino",
    "baccarat online",
    "roulette online",
    # Sports betting
    "taruhan bola",
    "taruhan online",
    "sbobet",
    "mix parlay",
    # Providers / brands (injected SEO)
    "pragmatic play",
    "pg soft",
    "habanero",
    "joker123",
    "spadegaming",
    "playtech",
    # Link / registration
    "link alternatif",
    "daftar sekarang",
    "bonus deposit",
    "deposit pulsa",
    "withdraw cepat",
]

# Patterns commonly found in injected anchor text
INJECTED_ANCHOR_PATTERNS: list[str] = [
    "slot",
    "gacor",
    "togel",
    "judi",
    "poker",
    "casino",
    "138",
    "777",
    "303",
    "4d",
    "sgp",
    "hk",
    "sydney",
    "sbobet",
    "maxwin",
]

# Google CSE dork query templates (% will be joined with domain target)
DORK_QUERIES: list[str] = [
    '"judi online"',
    '"slot gacor"',
    '"togel"',
    '"situs slot"',
    '"judi bola"',
    '"poker online"',
    '"casino online"',
    '"slot online"',
    '"bocoran slot"',
    '"link alternatif"',
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
