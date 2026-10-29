"""SHAP explanations for each engine's champion on its test window.

Global: mean |SHAP| per feature, grouped into graph vs profile (PRD pillar 'explainability').
Local: the three features that pushed each row's score up the most, for the app and the LLM.
Tree champions use TreeExplainer; Logistic Regression uses LinearExplainer; a rule baseline
is explained by its single rule feature.
"""
import joblib
import numpy as np
import pandas as pd
import shap

from src.config import path
from src.models.train import matrix

EMB = "emb_"
GRAPH_NAMES = {"pc_", "kemiripan_graph", "dot_graph", "pagerank", "porsi_bank", "tetangga", "log_nominal_dengan_bank",
               "bulan_aktif_dengan_bank", "log_masuk", "log_keluar", "n_pembayar", "n_penerima", "porsi_ke_rekening",
               "tren_porsi", "porsi_counterparty", "counterparty_baru", "transaksi_dengan_anchor"}


def group(feature: str, graph: list[str]) -> str:
    base = feature.split("_", 1)[0] if feature.startswith(EMB) else feature
    if feature.startswith(EMB) or feature.startswith("pc_") or any(feature.startswith(g) for g in graph):
        return "graph"
    return "profil"


def explain(engine: str, id_col: str, sample: int = 20000, seed: int = 42) -> dict:
    m = joblib.load(path("processed") / "models" / f"{engine}.pkl")
    scores = pd.read_parquet(path("processed") / "scores" / f"{engine}_test.parquet")
    feats = pd.read_parquet(path("processed") / "features" / FEATURE_FILE[engine])
    feats = feats[feats.index.isin(feats.index)]
    key = [id_col] + KEY_EXTRA.get(engine, [])
    test = scores[key].merge(feats, on=key, how="left", suffixes=("", "_f"))
    out_dir = path("processed") / "explain"
    out_dir.mkdir(parents=True, exist_ok=True)

    if m["champion"] == "Baseline bisnis":
        local = scores[key].assign(alasan_1=m["baseline"], nilai_1=scores[m["baseline"]].round(3), kontribusi_1=np.nan)
        local.to_parquet(out_dir / f"{engine}_lokal.parquet", index=False)
        glob = pd.DataFrame([{"fitur": m["baseline"], "mean_abs_shap": 1.0, "kelompok": group(m["baseline"], m["graph"])}])
        glob.to_csv(path("outputs") / "model" / f"{engine}_shap_global.csv", index=False)
        return {"porsi_graph": float(glob["kelompok"].eq("graph").mean())}

    X = matrix(test, m["features"], m["categories"]).reindex(columns=m["columns"], fill_value=0)
    model = m["model"]
    model = getattr(model, "estimator_", model)                   # oversampling wrapper: explain the inner LightGBM
    rng = np.random.default_rng(seed)
    idx = rng.choice(len(X), min(sample, len(X)), replace=False)
    if hasattr(model, "steps"):                                   # Logistic Regression pipeline
        lr = model.steps[-1][1]
        Z = pd.DataFrame(model[:-1].transform(X), columns=X.columns)
        sv = shap.LinearExplainer(lr, Z.iloc[idx]).shap_values(Z)
    else:
        sv = shap.TreeExplainer(model).shap_values(X)
        if isinstance(sv, list):
            sv = sv[1]
        if sv.ndim == 3:
            sv = sv[:, :, 1]
    sv = np.asarray(sv)

    glob = pd.DataFrame({"fitur": X.columns, "mean_abs_shap": np.abs(sv[idx]).mean(axis=0)})
    glob["kelompok"] = [group(f, m["graph"]) for f in glob["fitur"]]
    glob = glob.sort_values("mean_abs_shap", ascending=False)
    glob.to_csv(path("outputs") / "model" / f"{engine}_shap_global.csv", index=False)
    share = glob.groupby("kelompok")["mean_abs_shap"].sum()
    share = share / share.sum()

    # Local: top 3 positive contributions per row, embedding dims summarised as one 'graph embedding'.
    cols = np.array(X.columns)
    is_emb = np.array([c.startswith(EMB) for c in cols])
    named = sv[:, ~is_emb]
    names = cols[~is_emb]
    emb_total = sv[:, is_emb].sum(axis=1) if is_emb.any() else np.zeros(len(sv))
    contrib = np.column_stack([named, emb_total])
    names = np.append(names, "kemiripan_embedding_graph")
    values = np.column_stack([X.loc[:, ~is_emb].to_numpy(), np.full(len(X), np.nan)])
    top = np.argsort(-contrib, axis=1)[:, :3]
    local = test[key].copy()
    for r in range(3):
        local[f"alasan_{r + 1}"] = names[top[:, r]]
        local[f"nilai_{r + 1}"] = values[np.arange(len(X)), top[:, r]]
        local[f"kontribusi_{r + 1}"] = contrib[np.arange(len(X)), top[:, r]]
    local.to_parquet(out_dir / f"{engine}_lokal.parquet", index=False)
    return {"porsi_graph": float(share.get("graph", 0)), "porsi_profil": float(share.get("profil", 0))}


FEATURE_FILE = {"akuisisi": "akuisisi.parquet", "nbo": "nbo.parquet",
                **{f"akuisisi_{t}": "akuisisi.parquet" for t in ["perusahaan", "pedagang", "karyawan"]},
                **{f"wholesale_{n}": "wholesale.parquet" for n in
                   ["cross_sell_wholesale", "non_debitur_ke_debitur", "reaktivasi", "leakage"]}}
KEY_EXTRA = {"akuisisi": ["jendela_k"], "nbo": ["bulan_label", "produk"],
             **{f"akuisisi_{t}": ["jendela_k"] for t in ["perusahaan", "pedagang", "karyawan"]},
             **{f"wholesale_{n}": ["jendela_k"] for n in ["cross_sell_wholesale", "non_debitur_ke_debitur", "reaktivasi", "leakage"]}}
