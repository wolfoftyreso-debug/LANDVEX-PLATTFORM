"""Vad kunden kan BESLUTA – paketering efter beslutsförmåga, inte datamängd.

Landvex säljer inte tillgång till kartlager. Kunden köper förmågan att
avgöra något hon annars fått gissa. Paketeringen speglar därför beslut,
inte volym: varje nivå listar vilka frågor den låter dig avgöra, vem som
ställer dem och vilken endpoint som svarar.

Två spärrar, båda med samma skäl som resten av plattformen:

1. **Byggt eller planerat, aldrig otydligt.** Varje erbjudande bär
   `status`. Ett som säger `built` MÅSTE peka på en endpoint som finns –
   ett test hävdar det. En prislista som lovar obyggda funktioner är den
   kommersiella versionen av en påhittad siffra, och den upptäcks först
   när en kund betalat.

2. **Plan-id:n är ett kontrakt.** `free`/`pro`/`enterprise` sitter i
   API-nyckelformatet (`nyckel:tenant:roll:plan:tillägg`). Namnen på ytan
   ändras till Explorer/Professional/Enterprise Intelligence; id:na rörs
   inte, och alias gör att båda skrivsätten fungerar.

Rent stdlib.
"""
from __future__ import annotations

# status: built  = finns och kan användas idag
#         planned = beskriven, inte byggd. Får aldrig säljas som byggd.
DECISIONS: tuple[dict, ...] = (
    # ── Explorer ─────────────────────────────────────────────────────
    {"id": "understand_place", "audience": "citizen", "plan": "free", "status": "built",
     "question_en": "What is this place actually like?",
     "who_en": "Anyone curious about somewhere — a resident, a student.",
     "decides_en": "Whether a claim you heard about an area holds up.",
     "answered_by": "/v1/indices/assess"},
    {"id": "cite_a_figure", "audience": "journalist", "plan": "free",
     "status": "built",
     "question_en": "Can I quote this with a source that holds?",
     "who_en": "Journalists, editors and anyone who has to stand behind a "
               "figure in print.",
     "decides_en": "Whether the number is publishable — content-hashed, "
                   "versioned, and carrying its own citation.",
     "answered_by": "/v1/cite"},
    {"id": "check_a_claim", "audience": "citizen", "plan": "free", "status": "built",
     "question_en": "Is this figure unusual, or normal?",
     "who_en": "Anyone with a number they cannot place.",
     "decides_en": "Whether something is worth reacting to at all.",
     "answered_by": "/v1/benchmark"},
    # Publik med flit, och gratis med flit: en kund som måste FRÅGA vad
    # ett tal vilar på har redan fått fel produkt. Hela alt-data-segmentet
    # döljer att det är enkelkällat — att publicera sin egen täckning är
    # en kil, inte en svaghet.
    {"id": "coverage_here", "audience": "researcher", "plan": "free",
     "status": "built",
     "question_en": "What can you actually answer where I am?",
     "who_en": "Anyone about to trust a number — buyers, analysts, "
               "procurement, auditors.",
     "decides_en": "Whether the platform has anything real to say about "
                   "this market yet, and what it would take.",
     "answered_by": "/v1/coverage",
     "note_en": "Reports the share of each industry's WEIGHTED signal "
                "picture that a connected source can answer for in that "
                "market — not how many signals exist. Today that is 0.0 "
                "for every market except Sweden, and saying so before "
                "being asked is the point."},
    {"id": "public_brief", "audience": "citizen", "plan": "free", "status": "built",
     "question_en": "What changed that anyone may know about?",
     "who_en": "Anyone following a region.",
     "decides_en": "Whether to look closer. Public findings only.",
     "answered_by": "/v1/brief"},

    # ── Professional ─────────────────────────────────────────────────
    {"id": "where_to_establish", "audience": "business", "plan": "pro", "status": "built",
     "question_en": "Where does THIS business have the best chance?",
     "who_en": "Operators, consultants, brokers.",
     "decides_en": "Where to put your own money and years.",
     "answered_by": "/v1/report"},
    {"id": "is_the_market_full", "audience": "business", "plan": "pro", "status": "built",
     "question_en": "How saturated is this trade here?",
     "who_en": "Anyone entering a local market.",
     "decides_en": "Whether there is room, measured against comparable "
                   "places.",
     "answered_by": "/v1/saturation"},
    {"id": "what_will_be_needed", "audience": "municipality", "plan": "pro", "status": "built",
     "question_en": "What will this place be short of?",
     "who_en": "Municipalities, employers, training providers.",
     "decides_en": "What capacity to build before the shortage arrives.",
     "answered_by": "/v1/workforce/forecast"},
    {"id": "watch_my_interest", "audience": "municipality", "plan": "pro", "status": "built",
     "question_en": "Has anything I have a stake in moved?",
     "who_en": "Anyone with a stake in a place, trade or decision.",
     "decides_en": "When to look again — routed by what you have at stake.",
     "answered_by": "/v1/inbox/route"},
    {"id": "regional_brief", "audience": "business", "plan": "pro", "status": "built",
     "question_en": "What changed in my region and sector?",
     "who_en": "Anyone operating somewhere specific.",
     "decides_en": "What to examine this week, ranked by decision value.",
     "answered_by": "/v1/brief"},
    {"id": "worth_the_cost", "audience": "business", "plan": "pro", "status": "built",
     "question_en": "Is this worth what it costs?",
     "who_en": "Anyone weighing a spend against an uncertain return.",
     "decides_en": "Go or not — with the break-even probability stated.",
     "answered_by": "/v1/flows/expected-value"},
    {"id": "export_findings", "audience": "researcher", "plan": "pro", "status": "built",
     "question_en": "Can I take this into my own tools?",
     "who_en": "Consultants and analysts working in Excel or GIS.",
     "decides_en": "What to hand on — as CSV, NDJSON or GeoJSON, with the "
                   "caveats travelling inside the file.",
     "answered_by": "/v1/export",
     "note_en": "PDF, XLSX and Parquet are refused by name rather than "
                "approximated: they need rendering or columnar libraries "
                "the core does not take, and a CSV renamed .xlsx is a lie "
                "with an Excel icon on it. Exporting a dataset requires "
                "the same package as the endpoint it comes from."},

    # ── Enterprise Intelligence ──────────────────────────────────────
    {"id": "detect_without_asking", "audience": "investor", "plan": "enterprise", "status": "built",
     "question_en": "What should we know that nobody asked about?",
     "who_en": "Insurers, banks, utilities, infrastructure owners.",
     "decides_en": "Where to direct attention across a whole portfolio.",
     "answered_by": "/v1/brief"},
    {"id": "prove_assets_are_checked", "audience": "investor",
     "plan": "enterprise", "status": "built",
     "question_en": "Are our assets actually being checked — and can we "
                    "prove it?",
     "who_en": "Anyone responsible for physical objects in public: "
               "infrastructure owners, contractors, municipalities, "
               "insurers.",
     "decides_en": "Where to send someone this week, and what to hand an "
                   "auditor or an insurer after something has happened.",
     "answered_by": "/v1/inspections/compliance"},
    {"id": "own_detection_rules", "audience": "investor", "plan": "enterprise", "status": "built",
     "question_en": "Can we watch what matters to US, on our thresholds?",
     "who_en": "Organisations with their own risk definitions.",
     "decides_en": "What counts as an exception here — rules are data, so "
                   "new ones need no engine change.",
     "answered_by": "/v1/monitors"},
    {"id": "bind_decision_to_owner", "audience": "municipality", "plan": "enterprise", "status": "built",
     "question_en": "Who carries this decision, and did it work?",
     "who_en": "Boards, auditors, public bodies.",
     "decides_en": "Accountability — a commitment resolved against the "
                   "actual outcome.",
     "answered_by": "/v1/decisions/commit"},
    {"id": "machine_access", "audience": "researcher", "plan": "enterprise", "status": "built",
     "question_en": "Can our systems consume this directly?",
     "who_en": "Anyone integrating Landvex into their own stack.",
     "decides_en": "Whether to build on it — full API and agent manifest.",
     "answered_by": "/v1/agent-manifest"},
    # Nivån flyttad från enterprise till pro: Professional-planens egen
    # funktionslista lovade redan "scheduled watches (cron)". Två ställen
    # som säger olika om samma sak är ett prisfel, inte en detalj.
    {"id": "scheduled_runs", "audience": "researcher", "plan": "pro", "status": "built",
     "question_en": "Can it run itself on a schedule?",
     "who_en": "Operations teams.",
     "decides_en": "What happens without anyone asking — missions ordered "
                   "for what falls due, records recomputed, sweeps re-run "
                   "and stored.",
     "answered_by": "/v1/schedules",
     "note_en": "An in-process ticker (LANDVEX_SCHEDULER=on) or "
                "EventBridge/cron against POST /v1/schedules/run — both do "
                "the same work. Jobs are claimed in the store so two "
                "workers cannot run one job twice. A watch woken with no "
                "history to compare against skips with a stated reason "
                "rather than reporting calm. Scheduling is not a product "
                "of its own: each job kind requires the same package as "
                "the thing it runs, so an add-on customer can schedule "
                "what they bought without buying a tier for the timer."},
    {"id": "own_dashboards", "audience": "researcher", "plan": "enterprise", "status": "planned",
     "question_en": "Can we build our own views on it?",
     "who_en": "Larger organisations with internal reporting.",
     "decides_en": "Nothing yet — not built.",
     "answered_by": None,
     "note_en": "No dashboard builder exists. The API is what a dashboard "
                "would be built on."},
    {"id": "white_label", "audience": "business", "plan": "enterprise", "status": "planned",
     "question_en": "Can reports carry our own brand?",
     "who_en": "Advisors reselling analysis.",
     "decides_en": "Nothing yet — not built.",
     "answered_by": None},
)

# Ytnamn per nivå. Plan-id:t under är oförändrat (nyckelformatet är kontrakt).
PLAN_SURFACE: dict[str, dict] = {
    "free": {"name_en": "Explorer",
             "for_en": "Individuals, students and anyone exploring.",
             "promise_en": "See what the platform can do, on public "
                           "findings.",
             "billing_en": "Free. Not for commercial use.",
             "packagings": ("open",),
             "brief_scope": "public"},
    "pro": {"name_en": "Professional",
            "for_en": "Consultants, brokers, operators, municipalities and "
                      "smaller firms.",
            "promise_en": "Find the opportunity or the risk before the "
                          "competition does — in your region and trade.",
            # Tre sätt att köpa samma nivå, för att en franchise, en
            # kommun och en konsult inte kan köpa på samma villkor. Se
            # engine/commercial.py — meningen som stod här beskrev bara
            # ETT av dem och läste därför som en motsägelse mot sajten.
            "billing_en": "Three ways to buy this tier: commission per "
                          "delivered lead, per mission, or a three-month "
                          "pilot that becomes an annual subscription. Which "
                          "one fits depends on whether you have a purchase "
                          "order or a budget cycle — see /v1/commercial.",
            "packagings": ("per_lead", "per_mission",
                           "pilot_then_subscription"),
            "brief_scope": "region_sector"},
    "enterprise": {"name_en": "Enterprise Intelligence",
                   "for_en": "Larger firms, authorities, insurers, banks, "
                             "utilities and infrastructure owners.",
                   "promise_en": "A standing intelligence capability: your "
                                 "own rules, your own assets, decisions "
                                 "bound to owners.",
                   "billing_en": "A capability agreement, or a pilot that "
                                 "becomes one. By agreement — no list price "
                                 "is published, and none is invented here.",
                   "packagings": ("pilot_then_subscription",
                                  "capability_agreement"),
                   "brief_scope": "own_assets"},
}

# Explorer/Professional är ytnamn – id:t i nyckeln ändras aldrig.
SURFACE_ALIASES: dict[str, str] = {
    "explorer": "free", "professional": "pro",
    "enterprise intelligence": "enterprise", "growth": "pro",
}

BRIEF_SCOPES: dict[str, dict] = {
    "public": {"label_en": "Public findings only",
               "may_scope_by_area": False, "may_scope_by_sector": False,
               "may_use_own_assets": False,
               "why_en": "Shows the platform's reach without giving away "
                         "commercially useful specifics."},
    "region_sector": {"label_en": "Your region and sector",
                      "may_scope_by_area": True, "may_scope_by_sector": True,
                      "may_use_own_assets": False,
                      "why_en": "Scoped to where the subscriber actually "
                                "operates."},
    "own_assets": {"label_en": "Your own assets, suppliers and interests",
                   "may_scope_by_area": True, "may_scope_by_sector": True,
                   "may_use_own_assets": True,
                   "why_en": "The organisation's own brief, prioritised on "
                             "its holdings and dependencies."},
}


# Det ENA beslut som säljer nivån. Resten finns kvar och levereras — de
# ska bara inte vara det man möter. En prislista med sjutton punkter tvingar
# kunden att göra urvalet som säljaren borde ha gjort.
HEADLINE: dict[str, str] = {
    "free": "check_a_claim",
    "pro": "where_to_establish",
    "enterprise": "detect_without_asking",
}


def resolve_plan(name: str) -> str:
    """Ytnamn eller id → kanoniskt plan-id."""
    key = (name or "").strip().lower()
    return SURFACE_ALIASES.get(key, key)


def decisions_for(plan: str, include_planned: bool = True) -> list[dict]:
    """Beslut en nivå möjliggör. Nivåerna ärver nedåt."""
    plan = resolve_plan(plan)
    order = ["free", "pro", "enterprise"]
    if plan not in order:
        raise ValueError(f"unknown plan: {plan}. Choose {', '.join(order)}")
    allowed = set(order[:order.index(plan) + 1])
    return [dict(d) for d in DECISIONS
            if d["plan"] in allowed
            and (include_planned or d["status"] == "built")]


def brief_scope(plan: str) -> dict:
    plan = resolve_plan(plan)
    surf = PLAN_SURFACE.get(plan)
    if surf is None:
        raise ValueError(f"unknown plan: {plan}")
    return {"plan": plan, "scope": surf["brief_scope"],
            **BRIEF_SCOPES[surf["brief_scope"]]}


def offering(plan: str = "") -> dict:
    """Erbjudandet uttryckt i beslut, med byggt tydligt skilt från planerat."""
    plans = [resolve_plan(plan)] if plan else ["free", "pro", "enterprise"]
    out = []
    for p in plans:
        if p not in PLAN_SURFACE:
            raise ValueError(f"unknown plan: {p}")
        ds = decisions_for(p)
        built = [d for d in ds if d["status"] == "built"]
        planned = [d for d in ds if d["status"] == "planned"]
        # Ett beslut fram, resten kvar. Kunden ska kunna välja nivå på EN
        # mening; den som vill se allt öppnar `also_included`.
        head = next((d for d in built if d["id"] == HEADLINE[p]), None)
        out.append({
            "plan_id": p, **PLAN_SURFACE[p],
            "headline": head,
            "also_included": [d for d in built if d is not head],
            "decisions_you_can_make": built,
            "not_built_yet": planned,
            "built_count": len(built), "planned_count": len(planned),
            "brief": brief_scope(p),
        })
    return {
        "plans": out,
        "principle_en": "Landvex sells decision capability, not data access. "
                        "Each tier is described by the questions it lets you "
                        "settle, not by how many rows you may download.",
        "honesty_en": "Anything listed under not_built_yet does not exist. It "
                      "is shown so a plan cannot be sold on a feature that "
                      "has not been written — a test asserts every 'built' "
                      "decision points at an endpoint that actually exists.",
    }
