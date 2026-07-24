"""Demo: kör analyser och skriver ut rapporter i konceptdokumentets stil.

    python3 demo.py
"""
from __future__ import annotations

from engine.models import Location
from engine.scoring import analyze


def print_report(report) -> None:
    line = "─" * 46
    print(line)
    print(f"{report.vertical_label_sv.upper()}  ·  {report.location.address}")
    print(line)
    print(f"Opportunity Score   {int(report.opportunity_score)}/100")
    print()
    for f in report.factors:
        print(f"  {f.label_sv:<32}{int(f.score):>3}/100")
        if f.narrative_sv:
            print(f"    {f.narrative_sv}")
    print()
    print(f"Risk: {report.risk_level}. {report.risk_narrative_sv}")
    for ins in report.insights_sv:
        print(f"Insikt: {ins}")
    print()
    print(f"Rekommendation: \u201c{report.recommendation_sv}\u201d")
    print(f"(Datatäckning verkliga källor: {int(report.data_coverage * 100)} % – "
          f"resten simulerad i denna miljö)")
    print()


if __name__ == "__main__":
    cases = [
        (Location(59.3145, 18.0705, "Hornsgatan 52, Stockholm"), "frisor"),
        (Location(57.7005, 12.9405, "Borås villaområde"), "elektriker"),
        (Location(55.6055, 13.0005, "Malmö C-läge"), "cafe"),
    ]
    for loc, vertical in cases:
        print_report(analyze(loc, vertical))
