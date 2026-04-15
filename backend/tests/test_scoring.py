"""Unit tests for CVSS-lite scoring (no DB or network needed)."""

import pytest
from app.scanner.scoring import compute_cvss_lite


class TestBaseScores:
    def test_critical_base(self):
        # page_crawl critical gets module override 9.5
        score = compute_cvss_lite("critical", "page_crawl", [], [], False)
        assert score == 9.5

    def test_high_dork_sweep_override(self):
        # dork_sweep high -> 6.5 override
        score = compute_cvss_lite("high", "dork_sweep", [], [], False)
        assert score == 6.5

    def test_high_path_probe_override(self):
        score = compute_cvss_lite("high", "path_probe", [], [], False)
        assert score == 8.5

    def test_medium_path_probe_override(self):
        score = compute_cvss_lite("medium", "path_probe", [], [], False)
        assert score == 5.5

    def test_medium_header_probe_override(self):
        score = compute_cvss_lite("medium", "header_probe", [], [], False)
        assert score == 4.5

    def test_info_base(self):
        score = compute_cvss_lite("info", "cms_detect", [], [], False)
        assert score == 1.0

    def test_low_base(self):
        score = compute_cvss_lite("low", "header_probe", [], [], False)
        assert score == 3.0

    def test_unknown_severity_defaults_to_info(self):
        score = compute_cvss_lite("unknown", "cms_detect", [], [], False)
        assert score == 1.0


class TestEvidenceModifiers:
    def test_screenshot_adds_0_3(self):
        base = compute_cvss_lite("high", "cms_detect", [], [], False)
        with_screenshot = compute_cvss_lite("high", "cms_detect", [], [], True)
        assert round(with_screenshot - base, 1) == 0.3

    def test_five_keywords_adds_0_2(self):
        base = compute_cvss_lite("high", "cms_detect", [], [], False)
        with_kw = compute_cvss_lite("high", "cms_detect", ["a", "b", "c", "d", "e"], [], False)
        assert round(with_kw - base, 1) == 0.2

    def test_ten_keywords_adds_0_4(self):
        base = compute_cvss_lite("high", "cms_detect", [], [], False)
        with_kw = compute_cvss_lite("high", "cms_detect", list("abcdefghij"), [], False)
        assert round(with_kw - base, 1) == 0.4

    def test_ten_keywords_beats_five_keywords(self):
        five = compute_cvss_lite("high", "cms_detect", list("abcde"), [], False)
        ten = compute_cvss_lite("high", "cms_detect", list("abcdefghij"), [], False)
        assert ten > five

    def test_three_injected_links_adds_0_3(self):
        base = compute_cvss_lite("high", "cms_detect", [], [], False)
        with_links = compute_cvss_lite("high", "cms_detect", [], ["x", "y", "z"], False)
        assert round(with_links - base, 1) == 0.3

    def test_score_capped_at_10(self):
        # page_crawl critical (9.5) + screenshot (0.3) + 5 keywords (0.2) + 3 links (0.3) = 10.3 -> capped 10.0
        score = compute_cvss_lite(
            "critical", "page_crawl",
            ["a", "b", "c", "d", "e"],
            ["x", "y", "z"],
            True,
        )
        assert score == 10.0

    def test_fewer_than_5_keywords_no_modifier(self):
        base = compute_cvss_lite("high", "cms_detect", [], [], False)
        with_few_kw = compute_cvss_lite("high", "cms_detect", ["a", "b"], [], False)
        assert base == with_few_kw

    def test_fewer_than_3_links_no_modifier(self):
        base = compute_cvss_lite("high", "cms_detect", [], [], False)
        with_few_links = compute_cvss_lite("high", "cms_detect", [], ["a", "b"], False)
        assert base == with_few_links

    def test_score_is_rounded_to_1dp(self):
        score = compute_cvss_lite("high", "cms_detect", [], [], True)
        # Result should be a multiple of 0.1
        assert score == round(score, 1)
