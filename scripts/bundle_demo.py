"""Väver konsolen, ingången och rundturen till EN fil.

    python3 -m scripts.bundle_demo <konsol.html> <ut.html>

Tre ytor har levererats som tre separata artefakter: konsolen är
verktyget men förklarar ingenting, ingången förklarar allt men gör
ingenting, rundturen visar beteendet men saknar båda. Besökaren behövde
tre länkar och kunskap om i vilken ordning de öppnas.

Bygget är avsiktligt uppdelat i två steg i stället för en flagga på
`build_demo`: konsolen med full matris tar flera minuter och väger 42 MB,
och att bygga om den varje gång vävningen justeras vore slöseri på en
maskin som dessutom rullas tillbaka utan förvarning. Vävningen är en
strängoperation på en färdig fil och tar en sekund.

Så här hänger det ihop:

  * **Konsolen är basdokumentet.** Den äger `body`, flikraden och sin
    `MODE`-växling — och 99,9 % av byten.
  * **De två ytorna scopas** av `scripts/htmlscope.py` innan de vävs in,
    annars vinner det sist inlästa stilblocket.
  * **Klicket fångas i capture-fasen.** Konsolens flikhanterare sitter på
    `t.onclick`; en lyssnare på `document` i capture-läge hinner före och
    kan stoppa händelsen för de två nya lägena. Konsolens egen kod rörs
    därmed inte alls — och `LAGEN[MODE]`, som saknar poster för dem,
    hinner aldrig anropas.
  * **Ytorna är helbredds-lager**, inte vyer i sidopanelen. Panelen är
    300 px; en förklaringssida där hade varit oläslig.

Rent stdlib.
"""
from __future__ import annotations

import pathlib
import sys

_FLIKAR = (
    '<button class="tab" data-mode="ingang">'
    '<svg class="ikon"><use href="#i-kompass"/></svg>Start here</button>',
    '<button class="tab" data-mode="bevis">'
    '<svg class="ikon"><use href="#i-lager"/></svg>Evidence</button>',
)

_VAXLARE = """
<script>
/* Vävd av scripts/bundle_demo.py.
   Capture-fasen: konsolens flikhanterare ligger på elementets onclick, så
   en lyssnare här hinner före och kan stoppa händelsen innan den når
   knappen. Konsolens kod behöver därför inte ändras, och dess LAGEN-tabell
   — som inte har poster för de två nya lägena — anropas aldrig för dem. */
(function () {
  "use strict";
  var EGNA = { ingang: "ytaIngang", bevis: "ytaBevis" };
  function visa(mode) {
    var layout = document.querySelector(".layout");
    Object.keys(EGNA).forEach(function (m) {
      var el = document.getElementById(EGNA[m]);
      if (el) el.style.display = m === mode ? "" : "none";
    });
    if (layout) layout.style.display = EGNA[mode] ? "none" : "";
    window.scrollTo(0, 0);
  }
  document.addEventListener("click", function (e) {
    var t = e.target.closest ? e.target.closest(".tab") : null;
    if (!t) return;
    var mode = t.dataset.mode;
    document.querySelectorAll(".tab").forEach(function (x) {
      x.classList.toggle("on", x === t);
    });
    visa(mode);
    if (EGNA[mode]) {          // konsolens hanterare ska INTE köra
      e.stopPropagation();
      e.preventDefault();
    }
  }, true);

  /* Demon öppnar på förklaringen, inte på verktyget. Intro-overlayen
     tillhör konsolen och ska inte ligga över startytan. */
  document.addEventListener("DOMContentLoaded", function () {
    var intro = document.getElementById("intro");
    if (intro) intro.style.display = "none";
    document.querySelectorAll(".tab").forEach(function (x) {
      x.classList.toggle("on", x.dataset.mode === "ingang");
    });
    visa("ingang");
  });
})();
</script>
"""


def vav(konsol: str, ytor: list[tuple[str, str]]) -> str:
    """Väv in ytorna i konsoldokumentet.

    `ytor` = [(container_id, scopad_html), …] i flikordning.
    """
    if "</nav>" not in konsol:
        raise SystemExit("hittade ingen flikrad i konsolen")
    if "</body>" not in konsol:
        raise SystemExit("konsolen saknar </body> — inget ställe att väva i")

    ut = konsol.replace("</nav>", "".join(_FLIKAR) + "</nav>", 1)

    lager = []
    for cid, html in ytor:
        lager.append(
            f'<div id="{cid}" style="display:none;max-width:none">{html}</div>')
    ut = ut.replace("</body>", "".join(lager) + _VAXLARE + "</body>", 1)
    return ut


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__)
        return 64
    konsol_fil, ut_fil = pathlib.Path(argv[0]), pathlib.Path(argv[1])
    rot = pathlib.Path(__file__).resolve().parent.parent
    ingang = rot / ".build-ingang.html"
    bevis = rot / ".build-bevis.html"
    for f in (konsol_fil, ingang, bevis):
        if not f.exists():
            raise SystemExit(f"saknas: {f}")

    konsol = konsol_fil.read_text(encoding="utf-8")
    sida = vav(konsol, [
        ("ytaIngang", ingang.read_text(encoding="utf-8")),
        ("ytaBevis", bevis.read_text(encoding="utf-8")),
    ])
    ut_fil.write_text(sida, encoding="utf-8")
    print(f"{ut_fil} ({len(sida) // 1024} kB) · konsol + ingång + bevis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
