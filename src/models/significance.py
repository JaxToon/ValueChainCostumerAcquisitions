"""Is the champion really better than the baseline, and does the graph really help?

Paired bootstrap on the test window: the same resampled rows score both models, and the
difference in ROC-AUC / PR-AUC gets a 95% interval. An interval that excludes 0 means the
gain is unlikely to be luck. NBO has one row per person x product, so it is resampled by
person (cluster bootstrap). Also writes the calibration table (reliability plot): the
expected-value ranking (p x value - cost) is only right when p is calibrated.

    python -m pipelines.run_offline --only report   (runs this before writing Hasil_Model.md)
"""
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score, roc_auc_score

from src.config import path, settings

ENGINES = ["akuisisi", "akuisisi_perusahaan", "akuisisi_pedagang", "akuisisi_karyawan", "wholesale_cross_sell_wholesale",
           "wholesale_non_debitur_ke_debitur", "wholesale_reaktivasi", "wholesale_leakage", "nbo"]
PAIRS = [("skor", "skor_baseline", "Champion vs baseline bisnis"),
         ("skor_lightgbm_graph", "skor_lightgbm_tanpa_graph", "Ablation: LightGBM + graph vs tanpa graph")]
METRICS = {"roc_auc": roc_auc_score, "pr_auc": average_precision_score}


def _resample(df: pd.DataFrame, rng, B: int, cluster: str | None):
    if cluster is None:
        n = len(df)
        for _ in range(B):
            yield rng.integers(0, n, n)
        return
    groups = df.groupby(cluster).indices
    keys = np.array(list(groups))
    for _ in range(B):
        pick = rng.choice(len(keys), len(keys))
        yield np.concatenate([groups[keys[i]] for i in pick])


def paired(df: pd.DataFrame, a: str, b: str, B: int, cluster: str | None, seed: int) -> dict:
    y, sa, sb = df["label"].to_numpy(), df[a].to_numpy(), df[b].to_numpy()
    out = {}
    diffs = {m: [] for m in METRICS}
    rng = np.random.default_rng(seed)
    for idx in _resample(df, rng, B, cluster):
        yy = y[idx]
        if yy.min() == yy.max():
            continue
        for m, f in METRICS.items():
            diffs[m].append(f(yy, sa[idx]) - f(yy, sb[idx]))
    for m, f in METRICS.items():
        d = np.array(diffs[m])
        out[f"{m}_a"], out[f"{m}_b"] = f(y, sa), f(y, sb)
        out[f"{m}_selisih"] = out[f"{m}_a"] - out[f"{m}_b"]
        out[f"{m}_ci_bawah"], out[f"{m}_ci_atas"] = np.percentile(d, [2.5, 97.5])
        out[f"{m}_signifikan"] = bool(out[f"{m}_ci_bawah"] > 0 or out[f"{m}_ci_atas"] < 0)
    out["n_bootstrap"] = len(diffs["roc_auc"])
    return out


def calibration(df: pd.DataFrame, bins: int = 10) -> pd.DataFrame:
    """Observed conversion per decile of predicted probability; ECE = weighted |gap|."""
    q = pd.qcut(df["skor"].rank(method="first"), bins, labels=False)
    t = df.groupby(q).agg(prediksi_rata=("skor", "mean"), aktual=("label", "mean"), n=("label", "size")).reset_index(names="desil")
    t["ece"] = (t["n"] * (t["prediksi_rata"] - t["aktual"]).abs()).sum() / t["n"].sum()
    return t


def run(B: int = 1000) -> pd.DataFrame:
    seed = settings()["seed"]
    rows, cal = [], []
    for eng in ENGINES:
        f = path("processed") / "scores" / f"{eng}_test.parquet"
        if not f.exists():
            continue
        df = pd.read_parquet(f)
        cluster = "person_id" if eng == "nbo" else None
        for a, b, name in PAIRS:
            if a in df and b in df:
                rows.append({"mesin": eng, "uji": name, "model_a": df["model"].iloc[0] if a == "skor" else a,
                             **paired(df, a, b, 200 if eng == "nbo" else B, cluster, seed)})
        if df["model"].iloc[0] != "Baseline bisnis":
            cal.append(calibration(df).assign(mesin=eng))
        print(f"signifikansi {eng} selesai")
    res = pd.DataFrame(rows)
    out = path("outputs") / "model"
    res.to_csv(out / "signifikansi.csv", index=False)
    pd.concat(cal).to_csv(out / "kalibrasi.csv", index=False)
    return res


if __name__ == "__main__":
    print(run().round(3).to_string())
