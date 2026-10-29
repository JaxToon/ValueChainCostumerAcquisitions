"""Run DeepEval on the golden set and save the scores for the presentation:
outputs/eval/deepeval_skor.csv (one row per case and metric) and docs/Hasil_DeepEval.md.
Judge cost with gpt-4.1-mini is about $0.01 per case (DeepEval cache crashes on Windows, so it is off).

    python -m tests.eval_report              # all 45 quality cases, judged once
    python -m tests.eval_report --runs 3     # same outputs judged 3 times (PRD: average of 3 runs)
    python -m tests.eval_report --n 5        # quick check on the first 5
"""
import argparse
import time

import pandas as pd

from src.config import ROOT, path, settings
from tests.test_llm_eval import HAS_KEY, QUALITY, metrics_for, test_case

THRESHOLD_NOTE = ("faithfulness, kepatuhan pitch >= 0,8; relevansi, alasan kontekstual >= 0,7; PII leakage lolos = tidak bocor "
                  "(dinilai pada pitch eksternal, karena alasan internal memang untuk RM)")


def run(n: int | None = None, runs: int = 1) -> pd.DataFrame:
    """Generate each case once, then judge it `runs` times: the spread across runs is the
    judge's own variance, separate from the generator."""
    from deepeval import evaluate
    from deepeval.evaluate.configs import AsyncConfig, CacheConfig, DisplayConfig, ErrorConfig

    rows, cases = [], QUALITY[:n] if n else QUALITY
    for case in cases:
        t = time.time()
        tc, pitch, mode = test_case(case)
        gen_s = time.time() - t
        for run_no in range(1, runs + 1):
            main, pii = metrics_for(case)   # fresh metric objects per run
            for target, metrics in [(tc, main), (pitch, pii)]:
                res = evaluate([target], metrics, async_config=AsyncConfig(max_concurrent=5),
                               cache_config=CacheConfig(write_cache=False, use_cache=False),
                               display_config=DisplayConfig(print_results=False, show_indicator=False),
                               error_config=ErrorConfig(ignore_errors=True))
                for m in res.test_results[0].metrics_data or []:
                    rows.append({"run": run_no, "kasus": tc.name, "jenis": case["jenis"], "mode_generator": mode,
                                 "detik_generator": round(gen_s, 1), "metrik": m.name, "skor": m.score, "ambang": m.threshold,
                                 "lolos": m.success, "biaya_usd": m.evaluation_cost or 0.0, "alasan": (m.reason or "")[:300],
                                 "error": m.error, "output": target.actual_output[:1500]})
        print(f"{tc.name}: mode {mode}, {gen_s:.0f} s")
    df = pd.DataFrame(rows)
    out = path("outputs") / "eval"
    out.mkdir(parents=True, exist_ok=True)
    df.to_csv(out / "deepeval_skor.csv", index=False)
    write_md(df)
    return df


def write_md(df: pd.DataFrame):
    cfg = settings()["llm"]
    ok = df[df["error"].isna()]
    per = ok.groupby(["jenis", "metrik"]).agg(kasus=("kasus", "nunique"), skor_rata=("skor", "mean"), lolos=("lolos", "mean")).reset_index()
    modes = df.drop_duplicates("kasus")["mode_generator"].value_counts().to_dict()
    lines = ["# Hasil DeepEval", "",
             f"Dibuat otomatis oleh `python -m tests.eval_report`. Generator: `{cfg['model_generator']}` ({cfg['provider']}), "
             f"juri: `{cfg['model_juri']}`. Ambang: {THRESHOLD_NOTE}.", "",
             f"- Kasus kualitas: {df['kasus'].nunique()} (mode generator: {modes})",
             f"- Metrik lolos: {ok['lolos'].mean():.0%} dari {len(ok)} penilaian; error juri: {df['error'].notna().sum()}",
             f"- Biaya juri run ini: ${df['biaya_usd'].sum():.3f}",
             f"- Waktu generator rata-rata: {df.drop_duplicates('kasus')['detik_generator'].mean():.0f} detik per kasus",
             f"- Jumlah run juri: {df['run'].nunique()} (output generator sama di setiap run)", "",
             "| Jenis | Metrik | Kasus | Skor rata-rata | Lolos |", "|---|---|---|---|---|"]
    lines += [f"| {r.jenis} | {r.metrik} | {r.kasus} | {r.skor_rata:.2f} | {r.lolos:.0%} |" for r in per.itertuples()]
    if df["run"].nunique() > 1:
        v = ok.groupby(["metrik", "run"])["lolos"].mean().unstack()
        lines += ["", "## Variasi antar run juri", "",
                  "Output generator yang sama dinilai beberapa kali. Selisih antar run = ketidakpastian juri, bukan perubahan sistem.", "",
                  "| Metrik | Lolos rata-rata | Terendah | Tertinggi |", "|---|---|---|---|"]
        lines += [f"| {m} | {r.mean():.0%} | {r.min():.0%} | {r.max():.0%} |" for m, r in v.iterrows()]
        tot = ok.groupby("run")["lolos"].mean()
        lines += [f"| **Semua metrik** | **{tot.mean():.0%}** | {tot.min():.0%} | {tot.max():.0%} |"]
    fail = ok[~ok["lolos"].astype(bool)]
    if len(fail):
        lines += ["", "## Penilaian yang tidak lolos", "", "| Kasus | Metrik | Skor | Alasan juri |", "|---|---|---|---|"]
        lines += [f"| {r.kasus} | {r.metrik} | {r.skor:.2f} | {str(r.alasan).replace('|', '/').replace(chr(10), ' ')} |" for r in fail.itertuples()]
    lines += ["", "Serangan pada Tanya AI diuji terpisah tanpa juri: 5 kasus di `tests/test_llm_eval.py::test_serangan_ditolak` dan "
              "red team 25 serangan + 10 pertanyaan sah + 6 serangan baru di `tests/test_red_team.py`."]
    (ROOT / "docs" / "Hasil_DeepEval.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=None)
    ap.add_argument("--runs", type=int, default=1)
    args = ap.parse_args()
    if not HAS_KEY:
        raise SystemExit("OPENAI_API_KEY belum diisi di .env")
    d = run(args.n, args.runs)
    print(f"selesai: {d['kasus'].nunique()} kasus, biaya ${d['biaya_usd'].sum():.3f}")
