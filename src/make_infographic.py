"""Infografica HTML (self-contained) sui comuni che cambiano provincia/regione.

Legge comuni_assigned.geojson e produce outputs/infografica.html con:
  - KPI (totale, cambiano provincia, cambiano regione)
  - case study Robbio
  - top spostamenti per risparmio km
  - top cambi cross-regione
  - province che guadagnano/perdono più comuni (barre)
  - saldo per regione (barre)
"""
import sys
from pathlib import Path

import geopandas as gpd
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_PROCESSED, OUTPUTS, ROOT


def fmt(n):
    return f"{n:,}".replace(",", ".")


def bar_html(value, maxv, color, label, right=""):
    w = 100 * value / maxv if maxv else 0
    return (
        f'<div class="bar-row"><span class="bar-lbl">{label}</span>'
        f'<div class="bar-track"><div class="bar-fill" style="width:{w:.1f}%;background:{color}"></div></div>'
        f'<span class="bar-val">{right}</span></div>'
    )


def main() -> None:
    df = gpd.read_file(DATA_PROCESSED / "comuni_assigned.geojson").drop(columns="geometry")
    old_prov = gpd.read_file(DATA_PROCESSED / "old_provinces.geojson").drop(columns="geometry")
    reg = gpd.read_file(DATA_PROCESSED / "regioni.geojson").drop(columns="geometry")
    reg_name = dict(zip(reg["cod_reg"], reg["reg_name"]))
    sigla_name = dict(zip(old_prov["sigla"], old_prov["prov_name"]))

    df["old_reg"] = df["DEN_REG"]
    df["new_reg"] = df["new_cod_reg"].map(reg_name)

    total = len(df)
    n_prov = int(df["changed"].sum())
    n_reg = int(df["changed_region"].sum())
    pct_prov = 100 * n_prov / total
    pct_reg = 100 * n_reg / total

    moved = df[df["changed"]].copy()

    # top spostamenti (risparmio km)
    top_save = moved.nlargest(12, "delta_km")[
        ["COMUNE", "old_prov", "old_sigla", "new_prov", "new_sigla",
         "dist_old_km", "dist_new_km", "delta_km"]
    ]

    # top cross-regione
    cross = moved[moved["changed_region"]].nlargest(12, "delta_km")[
        ["COMUNE", "old_reg", "old_prov", "new_reg", "new_prov", "dist_old_km", "dist_new_km", "delta_km"]
    ]

    # saldi per provincia (sigla)
    gains = moved.groupby("new_sigla").size()
    losses = moved.groupby("old_sigla").size()
    sigle = sorted(set(gains.index) | set(losses.index))
    net = pd.Series({s: int(gains.get(s, 0) - losses.get(s, 0)) for s in sigle})
    top_gain = net.nlargest(8)
    top_loss = net.nsmallest(8).sort_values()  # più negativi

    # saldo per regione (solo cross-regione contano)
    cr = moved[moved["changed_region"]]
    g_reg = cr.groupby("new_reg").size()
    l_reg = cr.groupby("old_reg").size()
    regs = sorted(set(g_reg.index) | set(l_reg.index))
    net_reg = pd.Series({r: int(g_reg.get(r, 0) - l_reg.get(r, 0)) for r in regs}).sort_values()

    # ---- HTML ----
    def tbl_top_save():
        rows = ""
        for _, r in top_save.iterrows():
            rows += (
                f"<tr><td class='nome'>{r['COMUNE']}</td>"
                f"<td>{r['old_prov']} <span class='sig'>({r['old_sigla']})</span></td>"
                f"<td class='arrow'>→</td>"
                f"<td>{r['new_prov']} <span class='sig'>({r['new_sigla']})</span></td>"
                f"<td class='num'>{r['dist_old_km']:.0f}</td>"
                f"<td class='num'>{r['dist_new_km']:.0f}</td>"
                f"<td class='num gain'>−{r['delta_km']:.0f}</td></tr>"
            )
        return rows

    def tbl_cross():
        rows = ""
        for _, r in cross.iterrows():
            rows += (
                f"<tr><td class='nome'>{r['COMUNE']}</td>"
                f"<td>{r['old_reg']}<br><span class='sig'>{r['old_prov']}</span></td>"
                f"<td class='arrow'>→</td>"
                f"<td>{r['new_reg']}<br><span class='sig'>{r['new_prov']}</span></td>"
                f"<td class='num'>{r['dist_old_km']:.0f}</td>"
                f"<td class='num'>{r['dist_new_km']:.0f}</td>"
                f"<td class='num gain'>−{r['delta_km']:.0f}</td></tr>"
            )
        return rows

    maxabs = max(net.abs().max() if len(net) else 1, 1)
    bars_gain = "".join(
        bar_html(v, maxabs, "#2ca25f", f"{sigla_name.get(s, s)} ({s})", f"+{v}")
        for s, v in top_gain.items()
    )
    bars_loss = "".join(
        bar_html(-v, maxabs, "#d73027", f"{sigla_name.get(s, s)} ({s})", f"{v}")
        for s, v in top_loss.items()
    )

    maxabs_r = max(net_reg.abs().max() if len(net_reg) else 1, 1)
    bars_reg = ""
    for r, v in net_reg.items():
        col = "#2ca25f" if v >= 0 else "#d73027"
        right = f"+{v}" if v >= 0 else f"{v}"
        bars_reg += bar_html(abs(v), maxabs_r, col, r, right)

    robbio = df[df["COMUNE"] == "Robbio"].iloc[0]

    html = f"""<!doctype html>
<html lang="it"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Ridisegno delle province — infografica</title>
<style>
:root{{--fg:#1a1a1a;--muted:#666;--bg:#f7f7f5;--card:#fff;--line:#e3e3e0;
--accent:#ff7f00;--red:#d73027;--green:#2ca25f;--blue:#1f78b4}}
*{{box-sizing:border-box}}
body{{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;
color:var(--fg);background:var(--bg)}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 20px 60px}}
header h1{{font-size:30px;margin:0 0 4px}}
header p{{margin:0 0 6px;color:var(--muted)}}
.kpis{{display:flex;gap:14px;flex-wrap:wrap;margin:22px 0}}
.kpi{{flex:1;min-width:160px;background:var(--card);border:1px solid var(--line);
border-radius:10px;padding:16px 18px}}
.kpi .v{{font-size:34px;font-weight:700;line-height:1}}
.kpi .l{{color:var(--muted);font-size:13px;margin-top:6px}}
.kpi.accent .v{{color:var(--accent)}}
.kpi.red .v{{color:var(--red)}}
.callout{{background:#fff7ed;border:1px solid #fed7aa;border-left:5px solid var(--accent);
border-radius:8px;padding:14px 18px;margin:18px 0}}
.callout b{{color:#9a3412}}
section{{margin:30px 0}}
section h2{{font-size:19px;margin:0 0 4px}}
section .sub{{color:var(--muted);font-size:13px;margin:0 0 12px}}
table{{width:100%;border-collapse:collapse;background:var(--card);
border:1px solid var(--line);border-radius:8px;overflow:hidden;font-size:14px}}
th,td{{padding:7px 9px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:#f0f0ec;font-weight:600;font-size:12px;text-transform:uppercase;color:var(--muted)}}
td.num,th.num{{text-align:right;font-variant-numeric:tabular-nums}}
td.nome{{font-weight:600}}
.sig{{color:var(--muted);font-size:12px}}
.arrow{{color:var(--muted);text-align:center}}
.gain{{color:var(--green);font-weight:600}}
.two{{display:grid;grid-template-columns:1fr 1fr;gap:24px}}
@media(max-width:720px){{.two{{grid-template-columns:1fr}}.kpi .v{{font-size:28px}}}}
.bar-row{{display:flex;align-items:center;gap:8px;margin:5px 0;font-size:13px}}
.bar-lbl{{width:175px;flex-shrink:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}}
.bar-track{{flex:1;height:15px;background:#ececea;border-radius:3px;overflow:hidden}}
.bar-fill{{height:100%;border-radius:3px}}
.bar-val{{width:42px;text-align:right;font-variant-numeric:tabular-nums;font-weight:600}}
footer{{margin-top:34px;color:var(--muted);font-size:12px;border-top:1px solid var(--line);padding-top:12px}}
</style></head><body><div class="wrap">

<a href="index.html"
   style="position:fixed;top:14px;left:14px;z-index:9999;
          background:#ff7f00;color:#fff;padding:10px 18px;
          border-radius:8px;text-decoration:none;font:600 14px/1 Arial;
          box-shadow:2px 2px 6px rgba(0,0,0,.35);transition:background .2s"
   onmouseover="this.style.background='#e67300'"
   onmouseout="this.style.background='#ff7f00'">
   &#8592; Mappa
</a>

<header>
  <h1>Ridisegno delle province italiane</h1>
  <p>Se ogni comune andasse alla provincia col capoluogo più vicino (Voronoi sui 110 capoluoghi, distanza in linea d'aria)</p>
  <p>Fonte: confini ISTAT 2026 · capoluoghi geocodificati via Wikidata</p>
</header>

<div class="kpis">
  <div class="kpi"><div class="v">{fmt(total)}</div><div class="l">comuni italiani totali</div></div>
  <div class="kpi accent"><div class="v">{fmt(n_prov)}</div><div class="l">cambiano provincia ({pct_prov:.1f}%)</div></div>
  <div class="kpi red"><div class="v">{fmt(n_reg)}</div><div class="l">cambiano anche regione ({pct_reg:.1f}%)</div></div>
</div>

<div class="callout">
  <b>Caso di studio — Robbio.</b> In provincia di Pavia (Lombardia), dista {robbio['dist_old_km']:.0f} km da Pavia
  ma solo {robbio['dist_new_km']:.0f} km da Vercelli (Piemonte). Nel ridisegno passa alla
  <b>provincia di Vercelli</b>, cambiando regione: un esempio di come i confini attuali non seguano la vicinanza reale.
</div>

<section>
  <h2>Top spostamenti per risparmio di chilometri</h2>
  <p class="sub">Comuni che, passando al capoluogo più vicino, accorciano maggiormente la distanza dal capoluogo di provincia</p>
  <table>
    <tr><th>Comune</th><th>Da provincia</th><th></th><th>A provincia</th>
    <th class="num">Km prima</th><th class="num">Km dopo</th><th class="num">Risparmio</th></tr>
    {tbl_top_save()}
  </table>
</section>

<section>
  <h2>Cambi che attraversano i confini regionali</h2>
  <p class="sub">Top comuni il cui capoluogo più vicino sta in un'altra regione</p>
  <table>
    <tr><th>Comune</th><th>Da (regione/prov.)</th><th></th><th>A (regione/prov.)</th>
    <th class="num">Km prima</th><th class="num">Km dopo</th><th class="num">Risparmio</th></tr>
    {tbl_cross()}
  </table>
</section>

<div class="two">
<section>
  <h2>Province che guadagnano comuni</h2>
  <p class="sub">Saldo positivo (comuni in entrata − in uscita)</p>
  {bars_gain}
</section>
<section>
  <h2>Province che perdono comuni</h2>
  <p class="sub">Saldo negativo</p>
  {bars_loss}
</section>
</div>

<section>
  <h2>Saldo di comuni per regione</h2>
  <p class="sub">Solo i trasferimenti cross-regione muovono il saldo; rosso = regione perde comuni, verde = ne guadagna</p>
  {bars_reg}
</section>

<footer>
  Metodologia: per ogni comune (centro del poligono) si seleziona il capoluogo di provincia più vicino
  in linea d'aria (haversine). Le regioni restano invariate; le nuove province possono attraversarle.
  Su 110 province, 8 a capoluogo multiplo (Forlì-Cesena, Pesaro-Urbino, Massa-Carrara, BAT, Olbia-Tempio,
  Ogliastra, Medio Campidano, Carbonia-Iglesias) sono ridotte a un capoluogo unico. Distanze indicate in km.
</footer>

</div></body></html>"""

    ROOT.mkdir(parents=True, exist_ok=True)
    out = ROOT / "infografica.html"
    out.write_text(html, encoding="utf-8")
    print(f"Infografica salvata: {out} ({out.stat().st_size/1e3:.0f} KB)")
    print(f"  comuni totali: {total} | cambiano prov: {n_prov} ({pct_prov:.1f}%) | cambiano regione: {n_reg} ({pct_reg:.1f}%)")


if __name__ == "__main__":
    main()
