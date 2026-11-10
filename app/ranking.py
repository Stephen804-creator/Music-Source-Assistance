"""Explainable ranking for catalogue results; no model or external service required."""
from __future__ import annotations
import re
from typing import Any

def _words(value: Any) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", str(value or "").casefold()))

def score_track(track: dict[str, Any], interpretation: dict[str, Any]) -> tuple[float, list[str]]:
    fields = " ".join(str(track.get(k) or "") for k in ("title", "creator", "genre", "tags", "description", "provider"))
    words = _words(fields)
    score, reasons = 0.0, []
    attrs = interpretation.get("attributes", {})
    for group, concepts in attrs.items():
        for concept in concepts:
            concept_words = _words(concept)
            if concept_words and concept_words.issubset(words):
                weight = {"moods": 3.0, "genres": 3.5, "instruments": 3.0, "sound_types": 2.5, "production": 1.5}.get(group, 1.0)
                score += weight
                reasons.append(f"matches {concept}")
    duration = track.get("duration")
    target = interpretation.get("duration_target_seconds")
    if isinstance(duration, (int, float)) and target:
        ratio = min(float(duration), float(target)) / max(float(duration), float(target))
        score += ratio * 1.5
        if ratio >= 0.8: reasons.append("duration is close to target")
    if track.get("license") and str(track["license"]).casefold() not in {"unknown", "none", ""}:
        score += 0.5
        reasons.append("licence metadata is present")
    if track.get("source_url"):
        score += 0.5
        reasons.append("source page is available")
    if interpretation.get("constraints", {}).get("instrumental_only"):
        if any(term in words for term in ("instrumental", "no-vocals", "background")):
            score += 1.5; reasons.append("instrumental metadata match")
    return round(score, 3), reasons

def rank_tracks(tracks: list[dict[str, Any]], interpretation: dict[str, Any]) -> list[dict[str, Any]]:
    ranked = []
    for track in tracks:
        item = dict(track)
        score, reasons = score_track(item, interpretation)
        item["relevance_score"] = score
        item["match_reasons"] = reasons
        ranked.append(item)
    return sorted(ranked, key=lambda x: (x["relevance_score"], bool(x.get("source_url"))), reverse=True)
