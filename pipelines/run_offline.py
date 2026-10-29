"""Offline pipeline: clean data -> Neo4j graph -> graph algorithms -> features -> models.

    python -m pipelines.run_offline                 # all steps
    python -m pipelines.run_offline --from features # skip steps before 'features'
    python -m pipelines.run_offline --only models

Steps: clean, ingest (Neo4j), graph (GDS algorithms per window), features, models.
Results go to data/processed (read by the app) and outputs/ (reports).
"""
import argparse
import time

import pandas as pd

from src.config import path

STEPS = ["clean", "ingest", "graph", "features", "models", "explain", "report"]


def step_clean():
    from src.data.clean import clean_all, evaluate_cleaning
    rep = evaluate_cleaning(clean_all())
    rep.to_csv(path("outputs") / "cleaning_report.csv", index=False)
    print(rep.to_string(index=False))


def step_ingest():
    from src.graph.ingest import ingest
    print(ingest())


def step_graph():
    from src.graph.algorithms import run_all
    run_all()


def step_features():
    from src.features import acq_features, nbo_features, wholesale_features
    print("akuisisi", acq_features.build_all().shape)
    print("wholesale", wholesale_features.build_all().shape)
    print("nbo", nbo_features.build().shape)


def step_models():
    from src.features import acq_features as A, wholesale_features as W
    from src.models.train import compare
    rows = []
    d = pd.read_parquet(path("processed") / "features" / "akuisisi.parquet")
    d["sektor"] = d["sektor"].astype("category")
    emb = []   # raw embeddings are not comparable across windows; similarities are in A.GRAPH
    r = compare(d, "akuisisi", A.TABLE, A.GRAPH + emb, "log_nominal_total", d["jendela_k"] == 1, d["jendela_k"] == 2, trials=20)
    rows.append(r["tabel"].assign(mesin="akuisisi"))
    # Champion per prospect type (RM Commercial works the company list; traders and employees
    # go to anchor programmes). Each type may end with a different champion, even a rule.
    roles = {"perusahaan": d["tipe_perusahaan"] == 1, "pedagang": d["peran_pedagang"] == 1, "karyawan": d["peran_karyawan"] == 1}
    for tipe, mask in roles.items():
        x = d[mask]
        r = compare(x, f"akuisisi_{tipe}", A.TABLE, A.GRAPH + emb, "log_nominal_total", x["jendela_k"] == 1, x["jendela_k"] == 2, trials=15)
        rows.append(r["tabel"].assign(mesin=f"akuisisi_{tipe}"))

    w = pd.read_parquet(path("processed") / "features" / "wholesale.parquet")
    base = {"cross_sell_wholesale": "jumlah_produk_aktif", "non_debitur_ke_debitur": "log_saldo_rata2",
            "reaktivasi": "bulan_sejak_trade_selesai", "leakage": "porsi_ke_rekening_sendiri_bank_lain"}
    emb = []
    for name in W.LABELS:
        x = w[w[f"pool_{name}"] == 1].copy()
        x["label"] = x[f"label_{name}"]
        for c in ["segmen_bank", "sektor"]:
            x[c] = x[c].astype("category")
        r = compare(x, f"wholesale_{name}", W.TABLE, W.GRAPH + emb, base[name], x["jendela_k"] == 1, x["jendela_k"] == 2, trials=15)
        rows.append(r["tabel"].assign(mesin=f"wholesale_{name}"))

    from src.features import nbo_features as N
    n = pd.read_parquet(path("processed") / "features" / "nbo.parquet")
    test = max(n["bulan_label"])
    r = compare(n, "nbo", N.TABLE, N.GRAPH, "popularitas_produk", n["bulan_label"] < test, n["bulan_label"] == test,
                top=0.01, trials=15)
    rows.append(r["tabel"].assign(mesin="nbo"))
    s = pd.read_parquet(path("processed") / "scores" / "nbo_test.parquet")
    pd.DataFrame([{"model": r["champion"], **N.topk(s, "skor")}, {"model": "Baseline bisnis", **N.topk(s, "skor_baseline")}]).to_csv(
        path("outputs") / "model" / "nbo_topk.csv", index=False)

    allr = pd.concat(rows, ignore_index=True)
    allr.to_csv(path("outputs") / "model" / "ringkasan_model.csv", index=False)
    cols = ["mesin", "model", "pr_auc_validasi", "roc_auc", "pr_auc", "precision@10%", "lift_desil_1", "champion"]
    pd.set_option("display.width", 250)
    print(allr[cols].round(3).to_string(index=False))


ENGINES = {"akuisisi": "entity_id", "akuisisi_perusahaan": "entity_id", "akuisisi_pedagang": "entity_id",
           "akuisisi_karyawan": "entity_id", "nbo": "person_id",
           **{f"wholesale_{n}": "company_id" for n in ["cross_sell_wholesale", "non_debitur_ke_debitur", "reaktivasi", "leakage"]}}


def step_explain():
    from src.explain import fairness, neighbors, shap_explain
    rows = []
    for engine, key in ENGINES.items():
        rows.append({"mesin": engine, **shap_explain.explain(engine, key)})
        print(rows[-1], flush=True)
    pd.DataFrame(rows).to_csv(path("outputs") / "model" / "shap_porsi_graph.csv", index=False)
    neighbors.build()
    fairness.run()


def step_report():
    from src.models import significance
    from src.models.report import write
    significance.run()
    print(write())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--from", dest="start", choices=STEPS, default="clean")
    ap.add_argument("--only", choices=STEPS)
    a = ap.parse_args()
    todo = [a.only] if a.only else STEPS[STEPS.index(a.start):]
    for s in todo:
        t = time.time()
        print(f"== {s}", flush=True)
        globals()[f"step_{s}"]()
        print(f"   selesai {time.time() - t:.0f} detik", flush=True)


if __name__ == "__main__":
    main()
