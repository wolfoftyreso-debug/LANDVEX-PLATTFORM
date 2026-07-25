"""Ingångar – olika dörrar in, men varje dörr leder till ETT beslutssvar.

Kärnan: systemet är beslutsstöd, inte en analysplattform. Analys-lagren
(korrelation, scenario, benchmark, event-study …) är BEVISET; varje ingång
slutar i ett SVAR på rollens värdefulla beslutsfråga. `answered_by` är den
endpoint som KOMPONERAR svaret; `tools` är bevis-lagret bakom; `event_feeds`
är den event-drivna overlayen (motorn mäter kontinuerligt och pushar
rollens relevanta förändringar). Systemet rekommenderar aldrig — det ger
beslutsunderlaget + vem som bär utfallet; människan beslutar.

Rent data. Feed-koderna refererar `engine.feeds.FEEDS`.
"""
from __future__ import annotations

ENTRYPOINTS: tuple[dict, ...] = (
    {"id": "citizen", "label_en": "Citizen", "lens": "transparency",
     "visitor_en": "Someone who lives here and suspects their area is being short-changed.",
     "trigger_en": "A local claim in the news or a council meeting they cannot verify.",
     "success_en": "They can state whether the claim holds, with a source, and name who answers for it.",
     "question_en": "Is my area actually short on X — and who is responsible?",
     "decision_en": "Whether to act, and whom to hold to account.",
     "answered_by": "/v1/benchmark",
     "deliverable_en": "A benchmarked answer (outlier or normal vs peers) plus "
                       "the accountable owner from the ledger.",
     "tools": ["/v1/ask", "/v1/benchmark", "/v1/indices/assess",
               "/v1/corrections/submit", "/v1/decisions/ledger"],
     "event_feeds": ["daily_top_changes", "priority_alerts"]},
    {"id": "business", "label_en": "Business / entrepreneur", "lens": "opportunity",
     "visitor_en": "An operator about to commit their own money and years to one location.",
     "trigger_en": "They are choosing between places, or deciding whether to expand at all.",
     "success_en": "They can pick a location and defend the choice with drivers, risk and a plan.",
     "question_en": "Where does THIS business have the best chance to succeed?",
     "decision_en": "Where to establish, and on what terms.",
     "answered_by": "/v1/report",
     "deliverable_en": "A ranked establishment decision: score, drivers, risk, "
                       "plan and wages — the full decision card.",
     "tools": ["/v1/scan", "/v1/analyze", "/v1/plan", "/v1/opportunities",
               "/v1/wages/lookup", "/v1/wages/context"],
     "event_feeds": ["daily_top_changes", "regional_anomalies"]},
    {"id": "investor", "label_en": "Investor", "lens": "risk & return",
     "visitor_en": "Someone allocating capital who is judged on being right, later.",
     "trigger_en": "A thesis needs testing before it becomes a position.",
     "success_en": "They can size the bet, or walk away, knowing where the basis is thin.",
     "question_en": "What is the credible outlook, and where is it moving now?",
     "decision_en": "Go / watch / pass — you decide, on an honest basis.",
     "answered_by": "/v1/report",
     "deliverable_en": "A credibility-gated outlook + risk breakdown (refuses "
                       "when the basis is thin) so the call is yours, not faked.",
     "tools": ["/v1/scenario", "/v1/correlate", "/v1/gaps",
               "/v1/risk-intelligence", "/v1/indices/families"],
     "event_feeds": ["structural_decline", "priority_alerts"]},
    {"id": "municipality", "label_en": "Municipality / region", "lens": "stewardship",
     "visitor_en": "An official who must commit public money years before the need is visible.",
     "trigger_en": "Budget cycles, planning horizons, a shortage that is already forming.",
     "success_en": "They can fund the right capacity and bind each decision to an owner.",
     "question_en": "What do we need in 5–20 years, and who owns each outcome?",
     "decision_en": "What to invest in, with accountability bound to it.",
     "answered_by": "/v1/report",
     "deliverable_en": "A needs brief (workforce + gaps) with each decision "
                       "committed to a responsible owner and later resolved.",
     "tools": ["/v1/indices/families", "/v1/workforce/forecast",
               "/v1/gaps", "/v1/decisions/commit", "/v1/decisions/resolve"],
     "event_feeds": ["structural_decline", "regional_anomalies"]},
    {"id": "journalist", "label_en": "Journalist", "lens": "accountability",
     "visitor_en": "A reporter who has to publish something that will be attacked.",
     "trigger_en": "A figure is circulating and nobody can source it.",
     "success_en": "They can publish a verifiable, versioned claim — or show the claim fails.",
     "question_en": "What is actually true — with a source I can cite?",
     "decision_en": "Whether the claim holds — and how to cite it.",
     "answered_by": "/v1/cite",
     "deliverable_en": "A verifiable, versioned, citable finding (benchmark or "
                       "controlled correlation) — never a causal claim.",
     "tools": ["/v1/benchmark", "/v1/correlate", "/v1/sensitive-association",
               "/v1/cite", "/v1/decisions/ledger"],
     "event_feeds": ["priority_alerts", "regional_anomalies"]},
    {"id": "researcher", "label_en": "Researcher", "lens": "method",
     "visitor_en": "Someone who needs an effect to survive scrutiny, not to sound good.",
     "trigger_en": "A pattern looks real and must be tested against confounders.",
     "success_en": "They can state whether the effect holds under controls and replication.",
     "question_en": "Does the effect survive controls and replicate?",
     "decision_en": "Whether an effect is real enough to build on.",
     "answered_by": "/v1/event-study",
     "deliverable_en": "A controlled, replication-checked effect estimate with "
                       "confounders and assumptions explicit.",
     "tools": ["/v1/correlate", "/v1/event-study", "/v1/scenario",
               "/v1/sensitive-association", "/v1/setpoints/assess"],
     "event_feeds": ["regional_anomalies"]},
)

_BY_ID = {e["id"]: e for e in ENTRYPOINTS}


def entrypoints() -> list[dict]:
    """Alla ingångar – varje en beslutsresa (fråga → answered_by → svar)."""
    return [dict(e) for e in ENTRYPOINTS]


def entrypoint(entry_id: str) -> dict:
    e = _BY_ID.get(entry_id)
    if e is None:
        raise ValueError(f"unknown entrypoint: {entry_id}")
    return dict(e)
