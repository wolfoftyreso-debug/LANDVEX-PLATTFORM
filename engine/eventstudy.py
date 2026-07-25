"""Händelsestudie – före/efter en intervention, ärligt (dissg-anda).

För frågor som "hur påverkade cannabis-legaliseringen trafikolyckor?" är
naiv korrelation fel verktyg. Rätt verktyg är:

  * `before_after` – jämför nivå OCH tendens före vs efter ett brytdatum i
    EN jurisdiktion. Observationellt: andra samtidiga händelser är
    okontrollerade.
  * `diff_in_diff` – jämför förändringen i BEHANDLADE jurisdiktioner (som
    införde interventionen) mot KONTROLLER (som inte gjorde det), och nettar
    bort den gemensamma trenden. Det närmaste ett ärligt effektmått man
    kommer utan experiment – vilar på antagandet om parallella trender, som
    redovisas explicit.

Aldrig ett kausalt tvärsäkert påstående. Rent stdlib, bygger på
`engine.stats` + inramning ("statistik ljuger alltid").
"""
from __future__ import annotations

from .integrity import framing_disclosure
from .stats import linreg_trend, mean

CAVEAT = ("Observational, not an experiment. A before/after change can be "
          "driven by other events at the same time; a diff-in-diff nets out "
          "the common trend but relies on the parallel-trends assumption. "
          "Report of what the data shows, not proof of cause.")


def before_after(series: list[float], split_index: int, *,
                 metric: str = "indicator", event: str = "intervention") -> dict:
    """Jämför före `split_index` (interventionen) mot efter.

    Returnerar pre/post-medel, nivåförändring, och tendens före vs efter.
    """
    if not (0 < split_index < len(series)):
        raise ValueError("split_index must be within the series")
    pre, post = series[:split_index], series[split_index:]
    pre_m, post_m = mean(pre), mean(post)
    delta = post_m - pre_m
    delta_pct = (delta / abs(pre_m) * 100.0) if pre_m else 0.0
    pre_t = linreg_trend(pre) if len(pre) >= 2 else {"direction": "n/a"}
    post_t = linreg_trend(post) if len(post) >= 2 else {"direction": "n/a"}
    return {
        "metric": metric, "event": event, "split_index": split_index,
        "pre": {"n": len(pre), "mean": round(pre_m, 4),
                "trend": pre_t.get("direction")},
        "post": {"n": len(post), "mean": round(post_m, 4),
                 "trend": post_t.get("direction")},
        "level_change": round(delta, 4), "level_change_pct": round(delta_pct, 4),
        "trend_change": f"{pre_t.get('direction')} → {post_t.get('direction')}",
        "caveat": CAVEAT,
        "framing": framing_disclosure(
            {"design": "before/after (single unit)", "n_pre": len(pre),
             "n_post": len(post), "note": "other concurrent events uncontrolled"}),
    }


def diff_in_diff(treated_pre: list[float], treated_post: list[float],
                 control_pre: list[float], control_post: list[float], *,
                 metric: str = "indicator", event: str = "intervention") -> dict:
    """Difference-in-differences: behandlade vs kontroller, före vs efter.

    DiD = (behandlad_efter − behandlad_före) − (kontroll_efter − kontroll_före).
    Nettar bort den gemensamma trenden. Vilar på parallella-trender-antagandet.
    """
    t_change = mean(treated_post) - mean(treated_pre)
    c_change = mean(control_post) - mean(control_pre)
    did = t_change - c_change
    base = mean(treated_pre)
    did_pct = (did / abs(base) * 100.0) if base else 0.0
    return {
        "metric": metric, "event": event,
        "treated_change": round(t_change, 4),
        "control_change": round(c_change, 4),
        "did_estimate": round(did, 4),
        "did_pct_of_baseline": round(did_pct, 4),
        "reading": (f"After netting out the common trend, the treated group "
                    f"changed by {did:+.2f} relative to controls."),
        "assumption": ("Parallel trends: absent the intervention, treated and "
                       "control would have moved together. Verify pre-trends."),
        "caveat": CAVEAT,
        "framing": framing_disclosure(
            {"design": "difference-in-differences",
             "n_treated": len(treated_pre) + len(treated_post),
             "n_control": len(control_pre) + len(control_post),
             "note": "identifies an effect only if parallel-trends holds"}),
    }
