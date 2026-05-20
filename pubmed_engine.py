# pubmed_engine.py
# Phase 3: PubMed academic evidence layer for FlareTrack.
#
# Queries NCBI E-utilities to find papers linking patient diagnoses to detected
# triggers and correlated factors.  Results are cached locally as JSON files in
# data/pubmed_cache/ — no patient health data leaves the device; only generic
# medical vocabulary terms (diagnosis names, trigger words) are sent as query
# strings, which are indistinguishable from a standard PubMed search.
#
# 70/30 split: triggers backed by PubMed papers carry academic_weight=0.70;
# pattern-only triggers (no matching papers) carry user_pattern_weight=0.30.

import hashlib
import json
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


NCBI_BASE       = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
CACHE_TTL_DAYS  = 7
ACADEMIC_WEIGHT = 0.70
USER_WEIGHT     = 0.30
# NCBI allows max 3 requests/second without an API key; 0.35 s keeps us safely under.
REQUEST_DELAY   = 0.35

# Maps ai_engine feature field names to human-readable PubMed search terms.
FIELD_QUERY_TERMS: Dict[str, str] = {
    "stress_level":            "stress",
    "sleep_hours":             "sleep",
    "sleep_quality":           "sleep quality",
    "air_quality_index":       "air pollution",
    "barometric_pressure_hpa": "barometric pressure",
    "humidity_percent":        "humidity",
    "temperature_f":           "temperature",
    "exercise_minutes":        "exercise",
    "alcohol_units":           "alcohol",
    "caffeine_mg":             "caffeine",
    "hydration_oz":            "hydration",
}


class PubMedEngine:
    """Fetches and locally caches PubMed evidence for a patient's diagnoses and triggers.

    Two main entry points:
    - ``search(query)``            — cache-first low-level query
    - ``enrich_factor_report()``   — attaches evidence + 70/30 blend to a
                                     weighted_factor_report() dict
    """

    def __init__(
        self,
        cache_dir: str = "data/pubmed_cache",
        email: str = "",
        api_key: str = "",
    ):
        self.cache_dir = cache_dir
        self.email     = email
        self.api_key   = api_key
        os.makedirs(cache_dir, exist_ok=True)

    # =========================================================
    # CACHE
    # =========================================================

    def _cache_key(self, query: str) -> str:
        return hashlib.sha256(query.lower().strip().encode()).hexdigest()[:20]

    def _cache_path(self, key: str) -> str:
        return os.path.join(self.cache_dir, f"{key}.json")

    def _load_cache(self, key: str) -> Optional[Dict]:
        path = self._cache_path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as f:
                entry = json.load(f)
            if datetime.now() > datetime.fromisoformat(entry["expires_at"]):
                return None  # stale — will refetch from NCBI
            return entry
        except (json.JSONDecodeError, KeyError, ValueError, OSError):
            return None

    def _save_cache(self, key: str, query: str, results: List[Dict]) -> None:
        entry = {
            "query":        query,
            "cached_at":   datetime.now().isoformat(),
            "expires_at":  (datetime.now() + timedelta(days=CACHE_TTL_DAYS)).isoformat(),
            "result_count": len(results),
            "results":     results,
        }
        try:
            with open(self._cache_path(key), "w", encoding="utf-8") as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
        except OSError:
            pass  # non-fatal; next call will just fetch again

    # =========================================================
    # HTTP HELPERS
    # =========================================================

    def _base_params(self) -> Dict[str, str]:
        p: Dict[str, str] = {"tool": "FlareTrack"}
        if self.email:
            p["email"] = self.email
        if self.api_key:
            p["api_key"] = self.api_key
        return p

    def _get_json(self, endpoint: str, extra: Dict[str, str]) -> Optional[Dict]:
        params = {**self._base_params(), "retmode": "json", **extra}
        url    = f"{NCBI_BASE}/{endpoint}?{urlencode(params)}"
        try:
            req = Request(url, headers={"User-Agent": "FlareTrack/1.0"})
            with urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except (URLError, HTTPError, json.JSONDecodeError, OSError):
            return None

    def _get_xml(self, endpoint: str, extra: Dict[str, str]) -> Optional[ET.Element]:
        params = {**self._base_params(), **extra}
        url    = f"{NCBI_BASE}/{endpoint}?{urlencode(params)}"
        try:
            req = Request(url, headers={"User-Agent": "FlareTrack/1.0"})
            with urlopen(req, timeout=15) as resp:
                return ET.fromstring(resp.read().decode("utf-8"))
        except (URLError, HTTPError, ET.ParseError, OSError):
            return None

    # =========================================================
    # SEARCH AND FETCH
    # =========================================================

    def search(self, query: str, max_results: int = 5) -> List[Dict]:
        """Return up to ``max_results`` articles for *query*.
        Serves from local cache when available and not stale; fetches from NCBI otherwise."""
        key    = self._cache_key(query)
        cached = self._load_cache(key)
        if cached is not None:
            return cached["results"][:max_results]

        pmids = self._esearch(query, max_results)
        if not pmids:
            self._save_cache(key, query, [])
            return []

        time.sleep(REQUEST_DELAY)  # respect NCBI rate limit before second request
        articles = self._efetch(pmids)
        self._save_cache(key, query, articles)
        return articles

    def _esearch(self, query: str, max_results: int) -> List[str]:
        data = self._get_json("esearch.fcgi", {
            "db":     "pubmed",
            "term":   query,
            "retmax": str(max_results),
            "sort":   "relevance",
        })
        if data is None:
            return []
        try:
            return data["esearchresult"]["idlist"]
        except (KeyError, TypeError):
            return []

    def _efetch(self, pmids: List[str]) -> List[Dict]:
        if not pmids:
            return []
        root = self._get_xml("efetch.fcgi", {
            "db":      "pubmed",
            "id":      ",".join(pmids),
            "rettype": "abstract",
        })
        if root is None:
            return []
        return [self._parse_article(a) for a in root.findall(".//PubmedArticle")]

    @staticmethod
    def _parse_article(article: ET.Element) -> Dict:
        def el_text(path: str) -> str:
            node = article.find(path)
            return (node.text or "").strip() if node is not None else ""

        pmid  = el_text(".//PMID")
        title = el_text(".//ArticleTitle")

        medline = el_text(".//PubDate/MedlineDate")
        year    = el_text(".//PubDate/Year") or (medline[:4] if len(medline) >= 4 else "")

        # Abstract may be split into labelled sections (BACKGROUND, METHODS, …)
        parts = []
        for at in article.findall(".//AbstractText"):
            label   = at.get("Label", "")
            content = (at.text or "").strip()
            if content:
                parts.append(f"{label}: {content}" if label else content)
        abstract = " ".join(parts)

        authors = []
        for auth in article.findall(".//Author")[:3]:
            last     = (auth.findtext("LastName") or "").strip()
            initials = (auth.findtext("Initials") or "").strip()
            if last:
                authors.append(f"{last} {initials}".strip())

        return {
            "pmid":     pmid,
            "title":    title,
            "authors":  authors,
            "year":     year,
            "abstract": abstract,
            "url":      f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        }

    # =========================================================
    # HIGH-LEVEL ENTRY POINTS
    # =========================================================

    def query_for_diagnosis_and_triggers(
        self,
        diagnoses: List[str],
        triggers: List[str],
        max_results: int = 5,
    ) -> Dict[str, Any]:
        """Standalone lookup — returns PubMed papers for each trigger without
        needing a full weighted_factor_report dict."""
        if not diagnoses:
            return {"error": "No diagnoses provided", "evidence": {}}

        primary_dx = " ".join(diagnoses[:2])
        evidence: Dict[str, List[Dict]] = {}

        for trigger in triggers[:10]:
            query               = f'"{primary_dx}" "{trigger}" flare'
            evidence[trigger]   = self.search(query, max_results)
            time.sleep(REQUEST_DELAY)

        return {
            "diagnoses":         diagnoses,
            "triggers_searched": list(evidence.keys()),
            "evidence":          evidence,
        }

    def enrich_factor_report(
        self,
        report: Dict[str, Any],
        diagnoses: List[str],
        max_per_query: int = 3,
    ) -> Dict[str, Any]:
        """Attach PubMed evidence to a ``weighted_factor_report()`` dict.

        Searches for papers linking each top trigger and correlated environmental
        factor to the patient's diagnoses, then classifies each trigger as:
        - evidence-backed  → academic_weight  = 0.70
        - pattern-only     → user_pattern_weight = 0.30

        Returns a new dict (original is not mutated) with a ``pubmed_evidence``
        key added at the top level.
        """
        if not diagnoses:
            enriched = dict(report)
            enriched["pubmed_evidence"] = {
                "error": "No diagnoses on patient profile — add them in your profile to enable evidence lookup."
            }
            return enriched

        primary_dx   = " ".join(diagnoses[:2])
        top_triggers = report.get("top_triggers", [])
        top_factors  = list(report.get("top_correlated_factors", {}).keys())[:3]

        # --- Evidence for each top trigger ---
        trigger_evidence: Dict[str, List[Dict]] = {}
        for trigger in top_triggers[:5]:
            query                       = f'"{primary_dx}" "{trigger}" flare'
            trigger_evidence[trigger]   = self.search(query, max_per_query)
            time.sleep(REQUEST_DELAY)

        # --- Evidence for top correlated environmental factors ---
        factor_evidence: Dict[str, List[Dict]] = {}
        for field in top_factors:
            term               = FIELD_QUERY_TERMS.get(field, field.replace("_", " "))
            query              = f'"{primary_dx}" "{term}" pain'
            factor_evidence[field] = self.search(query, max_per_query)
            time.sleep(REQUEST_DELAY)

        # --- 70/30 split classification ---
        supported    = [t for t, papers in trigger_evidence.items() if papers]
        pattern_only = [t for t in top_triggers if t not in supported]
        sup_fraction = len(supported) / len(top_triggers) if top_triggers else 0.0
        # blended_confidence: how much of the risk picture has academic backing
        blended_conf = round(ACADEMIC_WEIGHT * sup_fraction + USER_WEIGHT, 2)

        enriched = dict(report)
        enriched["pubmed_evidence"] = {
            "query_timestamp":             datetime.now().isoformat(),
            "diagnoses_searched":          diagnoses,
            "trigger_evidence":            trigger_evidence,
            "factor_evidence":             factor_evidence,
            "academic_supported_triggers": supported,
            "pattern_only_triggers":       pattern_only,
            "evidence_blend": {
                "academic_weight":     ACADEMIC_WEIGHT,
                "user_pattern_weight": USER_WEIGHT,
                "supported_fraction":  round(sup_fraction, 2),
                "blended_confidence":  blended_conf,
            },
        }
        return enriched

    # =========================================================
    # CACHE UTILITIES
    # =========================================================

    def cache_stats(self) -> Dict[str, Any]:
        files      = [f for f in os.listdir(self.cache_dir) if f.endswith(".json")]
        total_size = sum(
            os.path.getsize(os.path.join(self.cache_dir, f)) for f in files
        )
        return {
            "cache_dir":       self.cache_dir,
            "cached_queries":  len(files),
            "total_size_kb":   round(total_size / 1024, 1),
            "ttl_days":        CACHE_TTL_DAYS,
        }

    def clear_cache(self) -> int:
        """Delete all cached query results. Returns number of files removed."""
        count = 0
        for fname in os.listdir(self.cache_dir):
            if fname.endswith(".json"):
                try:
                    os.remove(os.path.join(self.cache_dir, fname))
                    count += 1
                except OSError:
                    pass
        return count
