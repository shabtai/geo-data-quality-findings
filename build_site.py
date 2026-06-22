#!/usr/bin/env python3
"""Generate a static GitHub Pages site of GEO data-quality findings, per table.

Static output only (index.html + style.css + one page per table) — no build
step, GitHub Pages serves the files directly. Findings are tiered by downstream
impact; a finding marked verified was independently re-confirmed by a tool-based
verifier (computes evidence, judges it against the dataset's enrichment priors).
"""
import html
from pathlib import Path

OUT = Path(__file__).resolve().parent

# ---- findings data (organized per table) ---------------------------------
DATASETS = [
    {
        "acc": "GSE131907", "title": "Lung adenocarcinoma (single-cell, Korean cohort)",
        "domain": "scRNA-seq", "source": "ftp.ncbi.nlm.nih.gov/geo/series/GSE131nnn/GSE131907/",
        "tables": [
            {"name": "sample_metadata", "shape": "58 × 19", "desc": "Per-sample GEO metadata.",
             "findings": [
                {"tier": "critical", "verified": True, "t": "TNM stage contradicts metastasis site — sample mis-staged III instead of IV",
                 "where": "tissue origin abbrevation · tumor stage",
                 "d": "Sample NS_16 / patient P3016 is a brain metastasis (mBrain) but is staged III; all 9 other brain-metastasis samples are Stage IV. A distant metastasis is M1 → Stage IV by AJCC definition.",
                 "impact": "Mis-bins a patient in any stage-stratified survival / biomarker analysis."},
                {"tier": "critical", "verified": True, "t": "Expression matrix mislabeled — UMI counts presented as TPM",
                 "where": "description_2 · description_3",
                 "d": "The raw matrix is UMI counts while the normalized matrix is labeled log2TPM. TPM assumes full-length transcript coverage; 3′ UMI scRNA-seq should be CPM / log-normalized, not TPM.",
                 "impact": "Treating the matrix as TPM (cross-study comparison, length-normalized signatures) yields wrong expression."},
                {"tier": "moderate", "verified": False, "t": "Foreign-key fan-out — Patient id not unique",
                 "where": "patient id → PATIENT_FEATURE_SUMMARY.Patient id",
                 "d": "Cardinality ratio 0.7586 between the patient tables; a naive patient-level join multiplies rows. A circular join path was also detected.",
                 "impact": "Inflated n, deflated p-values, double-counted patients."},
             ]},
            {"name": "patient_feature_summary", "shape": "58 × 12", "desc": "Per-patient clinical table (from the Feature Summary workbook).",
             "findings": [
                {"tier": "cosmetic", "verified": False, "t": "Inconsistent clinical vocabularies / notation",
                 "where": "EGFR · Smoking · Pathology · Histology",
                 "d": "EGFR notation p.L858R vs L858R (+ stray whitespace); Smoking Never/Ex/Cur vs documented full terms; Pathology MD/PD/WD abbreviations; Histology ADC(Double).",
                 "impact": "Cohort fragmentation in naive groupby / value-matching; trivially normalized."},
             ]},
            {"name": "cell_annotation", "shape": "208,506 × 7", "desc": "Per-cell annotation (cell type, refined type, subtype).",
             "findings": [
                {"tier": "serious", "verified": True, "t": "Cell-type taxonomy interlock violated",
                 "where": "Cell_type · Cell_subtype",
                 "d": "244 cells are typed NK cells yet carry a T-cell subtype (CD8/CD4/Naive/Cytotoxic T); ~186 cells typed Fibroblasts carry endothelial subtypes. Subtype must be a subset of type; T and NK are distinct lineages.",
                 "impact": "Corrupts cell-type-stratified DE, deconvolution references, and cell–cell interaction analyses for those lineages."},
                {"tier": "cosmetic", "verified": False, "t": "Capitalization inconsistency",
                 "where": "Cell_type",
                 "d": "'MAST cells' is mis-capitalized as an acronym ('Mast' is a word, not an acronym).",
                 "impact": "Category fragmentation only."},
             ]},
        ],
    },
    {
        "acc": "GSE181919", "title": "Head & neck squamous cell carcinoma (single-cell)",
        "domain": "scRNA-seq", "source": "ftp.ncbi.nlm.nih.gov/geo/series/GSE181nnn/GSE181919/",
        "tables": [
            {"name": "sample_metadata", "shape": "37 × 15", "desc": "Per-sample GEO metadata.",
             "findings": [
                {"tier": "serious", "verified": True, "t": "Mislabeled column — 'disease stage' actually holds tissue type",
                 "where": "disease stage · source_name_ch1",
                 "d": "Values are CA / LN / NL / LP (primary cancer / lymph-node met / normal / leukoplakia), mapping 1:1 to source_name_ch1 — not cancer staging. There is no real disease-stage column.",
                 "impact": "Filtering or stratifying by 'disease stage' returns the tissue compartment instead — wrong cohorts."},
                {"tier": "moderate", "verified": True, "t": "Sample identifier trapped in free text",
                 "where": "title",
                 "d": "No dedicated sample-id column; the ID (C04, LN22, …) exists only as the trailing token of the free-text title (e.g. 'Primary cancer C04').",
                 "impact": "Naive joins to the per-cell table fail; the only robust link is via string parsing."},
             ]},
            {"name": "barcode_metadata", "shape": "54,239 × 8", "desc": "Per-cell barcode metadata.",
             "findings": [
                {"tier": "critical", "verified": False, "t": "Off-by-one header — per-cell annotations can be silently mislabeled",
                 "where": "(all columns)",
                 "d": "8 header names but 9 data columns (the leading cell-barcode column is unnamed — a classic R write.table rownames export). A naive read.table(header=TRUE) shifts every header left: Age becomes an expression metric, Sample-ID becomes cluster labels, and cell.type falls off the end.",
                 "impact": "Whole 54k-cell table mislabeled with no error. Reader-conditional: pandas' default recovers it (promotes the unnamed column to index); R / index-less readers do not."},
             ]},
        ],
    },
    {
        "acc": "GSE157103", "title": "COVID-19 (bulk RNA-seq, whole blood)",
        "domain": "bulk RNA-seq", "source": "ftp.ncbi.nlm.nih.gov/geo/series/GSE157nnn/GSE157103/",
        "tables": [
            {"name": "sample_metadata", "shape": "126 × 37", "desc": "Per-sample clinical metadata (labs, severity scores, demographics).",
             "findings": [
                {"tier": "serious", "verified": True, "t": "Ventilation contradiction",
                 "where": "mechanical ventilation · ventilator-free days",
                 "d": "3 patients have mechanical ventilation = yes and ventilator-free days = 28 (the maximum = 'never ventilated'). A ventilated patient cannot have 28 ventilator-free days.",
                 "impact": "Ventilator-free days is a standard COVID outcome endpoint; these 3 score as best-outcome despite being intubated."},
                {"tier": "serious", "verified": True, "t": "Non-ICU patients with an ICU-only severity score",
                 "where": "icu · apacheii",
                 "d": "8 patients have icu = no but a measured APACHE II score. APACHE II is an ICU severity score; non-ICU patients normally have it as 'unknown' (52/52 unknowns are non-ICU).",
                 "impact": "Mis-scores 8 patients on a severity variable used as a primary covariate."},
                {"tier": "moderate", "verified": False, "t": "Numeric lab columns polluted with text sentinels",
                 "where": "apacheii · sofa · lactate · fibrinogen · ddimer · procalcitonin · crp · ferritin · age",
                 "d": "Eight lab/severity columns carry the literal 'unknown'; one age is the corrupted value ':' (unrecoverable); two ages are capped >89 while their titles leak the exact age 90; lactate uses both 'unknown' and ''.",
                 "impact": "Silently coerces to NaN / breaks to_numeric across the most analytically important columns. Loud and recoverable."},
                {"tier": "moderate", "verified": False, "t": "Temporal integrity",
                 "where": "ventilator-free days · hospital-free days",
                 "d": "Implied ventilator days exceed implied hospital days for some rows.",
                 "impact": "Internally inconsistent durations."},
             ]},
        ],
    },
]

TIER_LABEL = {"critical": "Critical", "serious": "Serious", "moderate": "Moderate", "cosmetic": "Cosmetic"}
TIER_ORDER = ["critical", "serious", "moderate", "cosmetic"]


def esc(s): return html.escape(str(s))


def table_slug(acc, name): return f"{acc}__{name}".lower()


def head(title, depth=0):
    css = ("../" * depth) + "style.css"
    return (f"<!DOCTYPE html><html lang=en><head><meta charset=utf-8>"
            f"<meta name=viewport content='width=device-width,initial-scale=1'>"
            f"<title>{esc(title)}</title><link rel=stylesheet href='{css}'></head><body><div class=wrap>")


FOOT = ("<footer>Automated profiling + row-level audit of public NCBI&nbsp;GEO supplementary metadata, "
        "with headline findings re-confirmed by a tool-based verifier. "
        "Findings are data-quality hypotheses, not assertions about any downstream publication; "
        "impact statements are risks. Severity reflects downstream impact.</footer></div></body></html>")


def finding_card(f):
    badges = [f'<span class="b {f["tier"]}">{TIER_LABEL[f["tier"]]}</span>']
    if f.get("verified"):
        badges.append('<span class="b v">verified</span>')
    return (f'<div class="card {f["tier"]}">'
            f'<div class="t">{esc(f["t"])}</div>'
            f'<div class="where">{esc(f["where"])}</div>'
            f'<div class="d">{esc(f["d"])}</div>'
            f'<div class="impact">Risk: {esc(f["impact"])}</div>'
            f'<div class="badges">{"".join(badges)}</div></div>')


def build():
    # per-table pages
    for ds in DATASETS:
        for tbl in ds["tables"]:
            slug = table_slug(ds["acc"], tbl["name"])
            fs = sorted(tbl["findings"], key=lambda f: TIER_ORDER.index(f["tier"]))
            body = [head(f'{ds["acc"]} · {tbl["name"]}')]
            body.append('<a class="back" href="index.html">← all tables</a>')
            body.append(f'<h1>{esc(tbl["name"])}</h1>')
            body.append(f'<p class="sub">{esc(ds["acc"])} — {esc(ds["title"])} · <span class="mono">{esc(tbl["shape"])}</span></p>')
            body.append(f'<p class="desc">{esc(tbl["desc"])}</p>')
            body.append(f'<p class="count">{len(fs)} finding(s)</p>')
            body += [finding_card(f) for f in fs]
            body.append(FOOT)
            (OUT / f"{slug}.html").write_text("".join(body))

    # index
    n_find = sum(len(t["findings"]) for d in DATASETS for t in d["tables"])
    n_tbl = sum(len(d["tables"]) for d in DATASETS)
    n_ver = sum(1 for d in DATASETS for t in d["tables"] for f in t["findings"] if f.get("verified"))
    b = [head("GEO Metadata — Data-Quality Findings")]
    b.append("<h1>GEO Metadata — Data-Quality Findings</h1>")
    b.append('<p class="sub">Automated profiling and row-level audit of three public NCBI&nbsp;GEO supplementary-metadata datasets — findings per table, each headline finding re-confirmed by a tool-based verifier.</p>')
    b.append('<div class="grid">'
             f'<div class="stat"><div class="n">{len(DATASETS)}</div><div class="l">Datasets</div></div>'
             f'<div class="stat"><div class="n">{n_tbl}</div><div class="l">Tables</div></div>'
             f'<div class="stat"><div class="n">{n_find}</div><div class="l">Findings</div></div>'
             f'<div class="stat"><div class="n">{n_ver}</div><div class="l">Verified</div></div></div>')
    for ds in DATASETS:
        b.append(f'<div class="ds"><h2>{esc(ds["acc"])} <span class="dim">— {esc(ds["title"])}</span></h2>')
        b.append(f'<p class="meta">{esc(ds["domain"])} · <span class="mono">{esc(ds["source"])}</span></p>')
        for tbl in ds["tables"]:
            slug = table_slug(ds["acc"], tbl["name"])
            tiers = {}
            for f in tbl["findings"]:
                tiers[f["tier"]] = tiers.get(f["tier"], 0) + 1
            chips = "".join(f'<span class="b {t}">{tiers[t]} {TIER_LABEL[t].lower()}</span>'
                            for t in TIER_ORDER if t in tiers)
            b.append(f'<a class="trow" href="{slug}.html">'
                     f'<span class="tn mono">{esc(tbl["name"])}</span>'
                     f'<span class="ts mono">{esc(tbl["shape"])}</span>'
                     f'<span class="tc">{chips}</span></a>')
        b.append("</div>")
    b.append(FOOT)
    (OUT / "index.html").write_text("".join(b))

    (OUT / "style.css").write_text(CSS)
    print(f"built: index.html + {n_tbl} table pages + style.css  ({n_find} findings, {n_ver} verified)")


CSS = """
:root{--bg:#0f1419;--panel:#171d26;--panel2:#1e2630;--ink:#e7edf3;--muted:#94a3b3;--line:#2a323d;
--accent:#5aa9ff;--crit:#ff6b6b;--serious:#ffa94d;--mod:#ffe066;--cos:#74c0fc;--ok:#51cf66;}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:900px;margin:0 auto;padding:44px 22px 80px}
h1{font-size:29px;margin:0 0 6px;letter-spacing:-.01em}
h2{font-size:19px;margin:30px 0 4px}
.dim{color:var(--muted);font-weight:400}
.sub{color:var(--muted);margin:0 0 22px}
.desc{color:var(--muted)}.count{color:var(--muted);font-size:13px;text-transform:uppercase;letter-spacing:.04em}
.mono{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin:20px 0 8px}
.stat{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:14px 16px}
.stat .n{font-size:25px;font-weight:700}.stat .l{color:var(--muted);font-size:11px;text-transform:uppercase;letter-spacing:.05em}
.ds{margin:26px 0}
.meta{color:var(--muted);font-size:13px;margin:2px 0 12px}
.trow{display:flex;align-items:center;gap:14px;background:var(--panel);border:1px solid var(--line);
border-radius:9px;padding:12px 15px;margin:8px 0;text-decoration:none;color:var(--ink);transition:.12s}
.trow:hover{border-color:var(--accent);background:var(--panel2)}
.tn{flex:0 0 230px;color:var(--accent)}.ts{flex:0 0 110px;color:var(--muted)}.tc{flex:1;text-align:right}
.back{color:var(--accent);text-decoration:none;font-size:13px}.back:hover{text-decoration:underline}
.card{background:var(--panel2);border:1px solid var(--line);border-left:3px solid var(--line);
border-radius:8px;padding:13px 15px;margin:11px 0}
.card.critical{border-left-color:var(--crit)}.card.serious{border-left-color:var(--serious)}
.card.moderate{border-left-color:var(--mod)}.card.cosmetic{border-left-color:var(--cos)}
.card .t{font-weight:650;margin:0 0 5px}
.card .where{font-family:ui-monospace,Menlo,monospace;font-size:12px;color:var(--accent);background:#0d1117;
padding:1px 7px;border-radius:4px;display:inline-block;margin-bottom:6px}
.card .d{color:#c6d2de;font-size:13.5px;margin:5px 0}
.card .impact{color:#ffd8a8;font-size:13px;margin-top:5px}
.badges{margin-top:8px;display:flex;gap:6px;flex-wrap:wrap}
.b{font-size:11px;padding:2px 9px;border-radius:20px;border:1px solid var(--line);color:var(--muted);white-space:nowrap}
.b.critical{color:var(--crit);border-color:#54262a}.b.serious{color:var(--serious);border-color:#553f23}
.b.moderate{color:var(--mod);border-color:#544e23}.b.cosmetic{color:var(--cos);border-color:#23415c}
.b.v{color:var(--ok);border-color:#234d2e}
footer{margin-top:44px;padding-top:18px;border-top:1px solid var(--line);color:var(--muted);font-size:12px}
a{color:var(--accent)}
"""

if __name__ == "__main__":
    build()
