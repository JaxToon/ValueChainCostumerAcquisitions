"""Train and compare models on walk-forward windows: fit on the earlier window, score the
later one. Shared by the acquisition, wholesale and NBO engines.

Models: business baseline (one score column), Logistic Regression, Random Forest, XGBoost,
LightGBM without graph features, LightGBM with graph features (tuned with Optuna on a
holdout of the training window, then calibrated with isotonic regression).
Imbalance: class weights / scale_pos_weight on the training window only, plus one candidate
that random-oversamples the positives instead (grill me Q23), so the two are compared on the
same validation split.
"""
import re

import joblib
import lightgbm as lgb
import numpy as np
import optuna
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (accuracy_score, average_precision_score, brier_score_loss, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler
from xgboost import XGBClassifier

from src.config import path, settings

optuna.logging.set_verbosity(optuna.logging.WARNING)


def matrix(df: pd.DataFrame, cols: list[str], categories: dict | None = None) -> pd.DataFrame:
    """Numeric design matrix; categorical columns become one-hot with fixed categories."""
    X = df[cols].copy()
    cats = [c for c in cols if isinstance(X[c].dtype, pd.CategoricalDtype) or X[c].dtype == object]
    for c in cats:
        levels = categories[c] if categories else sorted(X[c].astype(str).unique())
        X[c] = pd.Categorical(X[c].astype(str), categories=levels)
    X = pd.get_dummies(X, columns=cats, dtype=float)
    X.columns = [re.sub(r"[^0-9A-Za-z_]", "_", str(c)) for c in X.columns]   # LightGBM rejects JSON characters
    return X.astype(float).fillna(0)


class OverSampled(ClassifierMixin, BaseEstimator):
    """Random oversampling of the positive class before fitting (training rows only)."""

    def __init__(self, estimator=None, seed: int = 42):
        self.estimator = estimator
        self.seed = seed

    def fit(self, X, y):
        y = np.asarray(y)
        pos, neg = np.flatnonzero(y == 1), np.flatnonzero(y == 0)
        extra = np.random.default_rng(self.seed).choice(pos, max(len(neg) - len(pos), 0), replace=True)
        idx = np.concatenate([np.arange(len(y)), extra])
        self.estimator_ = clone(self.estimator).fit(X.iloc[idx] if hasattr(X, "iloc") else X[idx], y[idx])
        self.classes_ = self.estimator_.classes_
        return self

    def predict_proba(self, X):
        return self.estimator_.predict_proba(X)


def slug(name: str) -> str:
    return re.sub(r"[^0-9a-z]+", "_", name.lower()).strip("_")


def metrics(y: np.ndarray, s: np.ndarray, top: float) -> dict:
    """Ranking metrics plus classification metrics at the operational cut-off (top share)."""
    k = max(int(round(len(s) * top)), 1)
    order = np.argsort(-s)
    pred = np.zeros(len(s), dtype=int)
    pred[order[:k]] = 1
    base = y.mean()
    return {"roc_auc": roc_auc_score(y, s), "pr_auc": average_precision_score(y, s),
            f"precision@{top:.0%}": y[order[:k]].mean(), f"recall@{top:.0%}": y[order[:k]].sum() / max(y.sum(), 1),
            "lift_desil_1": y[order[:max(len(s) // 10, 1)]].mean() / base if base else np.nan,
            "accuracy": accuracy_score(y, pred), "precision": precision_score(y, pred, zero_division=0),
            "recall": recall_score(y, pred), "f1": f1_score(y, pred)}


def tune_lgbm(X: pd.DataFrame, y: np.ndarray, trials: int, seed: int) -> dict:
    Xa, Xb, ya, yb = train_test_split(X, y, test_size=0.25, stratify=y, random_state=seed)
    spw = (len(ya) - ya.sum()) / max(ya.sum(), 1)

    def objective(trial):
        p = {"n_estimators": trial.suggest_int("n_estimators", 150, 700, step=50),
             "learning_rate": trial.suggest_float("learning_rate", 0.01, 0.1, log=True),
             "num_leaves": trial.suggest_int("num_leaves", 15, 63),
             "min_child_samples": trial.suggest_int("min_child_samples", 20, 200),
             "subsample": trial.suggest_float("subsample", 0.6, 1.0), "subsample_freq": 1,
             "colsample_bytree": trial.suggest_float("colsample_bytree", 0.4, 1.0),
             "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 5.0)}
        m = lgb.LGBMClassifier(**p, scale_pos_weight=spw, random_state=seed, verbose=-1).fit(Xa, ya)
        return average_precision_score(yb, m.predict_proba(Xb)[:, 1])

    study = optuna.create_study(direction="maximize", sampler=optuna.samplers.TPESampler(seed=seed))
    study.optimize(objective, n_trials=trials)
    return {**study.best_params, "subsample_freq": 1}


def candidates(spw: float, seed: int, best: dict) -> dict:
    """name -> (factory, uses graph features). Factories return fresh, unfitted models."""
    return {
        # Standardised values are clipped to +-5 so a feature that is almost constant in the
        # training window cannot saturate the score when it shifts in a later window.
        "Logistic Regression": (lambda: make_pipeline(StandardScaler(), FunctionTransformer(np.clip, kw_args={"a_min": -5, "a_max": 5}),
                                                      LogisticRegression(max_iter=2000, class_weight="balanced", C=0.5)), True),
        "Random Forest": (lambda: RandomForestClassifier(n_estimators=300, min_samples_leaf=20, class_weight="balanced_subsample",
                                                         n_jobs=-1, random_state=seed), True),
        "XGBoost": (lambda: XGBClassifier(n_estimators=400, max_depth=5, learning_rate=0.05, subsample=0.8, colsample_bytree=0.7,
                                          scale_pos_weight=spw, random_state=seed, n_jobs=-1, eval_metric="aucpr"), True),
        "LightGBM tanpa graph": (lambda: lgb.LGBMClassifier(n_estimators=400, learning_rate=0.03, num_leaves=31,
                                                            scale_pos_weight=spw, random_state=seed, verbose=-1), False),
        "LightGBM + graph": (lambda: lgb.LGBMClassifier(**best, scale_pos_weight=spw, random_state=seed, verbose=-1), True),
        "LightGBM + graph (oversampling)": (lambda: OverSampled(lgb.LGBMClassifier(**best, random_state=seed, verbose=-1), seed), True),
    }


def compare(df: pd.DataFrame, engine: str, table: list[str], graph: list[str], baseline: str,
            train_mask: pd.Series, test_mask: pd.Series, label: str = "label", top: float = 0.10,
            trials: int = 25) -> dict:
    """Fit every model on the training window, pick the champion by PR-AUC on a holdout of
    the training window (never on the test window), calibrate it, and report all models
    on the test window."""
    seed = settings()["seed"]
    tr, te = df[train_mask], df[test_mask]
    ytr, yte = tr[label].to_numpy(), te[label].to_numpy()
    full = table + graph
    cats = {c: sorted(df[c].astype(str).unique()) for c in full
            if isinstance(df[c].dtype, pd.CategoricalDtype) or df[c].dtype == object}
    X = {True: (matrix(tr, full, cats), matrix(te, full, cats)), False: (matrix(tr, table, cats), matrix(te, table, cats))}
    spw = (len(ytr) - ytr.sum()) / max(ytr.sum(), 1)
    best = tune_lgbm(X[True][0], ytr, trials, seed)
    models = candidates(spw, seed, best)

    # Validation: 75/25 split of the training window.
    ia, ib = train_test_split(np.arange(len(ytr)), test_size=0.25, stratify=ytr, random_state=seed)
    val = {"Baseline bisnis": average_precision_score(ytr[ib], tr[baseline].to_numpy()[ib])}
    for name, (make, g) in models.items():
        Xa = X[g][0].iloc[ia]
        val[name] = average_precision_score(ytr[ib], make().fit(Xa, ytr[ia]).predict_proba(X[g][0].iloc[ib])[:, 1])
    champion = max(val, key=val.get)

    scores, fitted = {"Baseline bisnis": te[baseline].to_numpy()}, {}
    for name, (make, g) in models.items():
        fitted[name] = make().fit(X[g][0], ytr)
        scores[name] = fitted[name].predict_proba(X[g][1])[:, 1]
    if champion != "Baseline bisnis":
        make, g = models[champion]
        cal = CalibratedClassifierCV(make(), method="isotonic", cv=5).fit(X[g][0], ytr)
        champ_score = cal.predict_proba(X[g][1])[:, 1]
    else:
        cal, g, champ_score = None, True, scores["Baseline bisnis"]

    rows = [{"model": name, "pr_auc_validasi": val[name], **metrics(yte, sc, top)} for name, sc in scores.items()]
    result = pd.DataFrame(rows)
    result["champion"] = (result["model"] == champion).astype(int)
    result["n_train"], result["positif_train"] = len(ytr), int(ytr.sum())
    result["n_test"], result["positif_test"] = len(yte), int(yte.sum())
    result["brier_champion"] = np.nan
    if cal is not None:
        result.loc[result["champion"] == 1, "brier_champion"] = brier_score_loss(yte, champ_score)

    out = path("outputs") / "model"
    out.mkdir(parents=True, exist_ok=True)
    result.to_csv(out / f"{engine}_perbandingan.csv", index=False)
    mdir = path("processed") / "models"
    mdir.mkdir(parents=True, exist_ok=True)
    joblib.dump({"champion": champion, "calibrated": cal, "model": fitted.get(champion), "uses_graph": g,
                 "columns": list(X[g][0].columns), "categories": cats, "features": full if g else table,
                 "table": table, "graph": graph, "baseline": baseline, "lgbm_params": best,
                 "lgbm_graph": fitted["LightGBM + graph"], "columns_full": list(X[True][0].columns)}, mdir / f"{engine}.pkl")
    sdir = path("processed") / "scores"
    sdir.mkdir(parents=True, exist_ok=True)
    keep = [c for c in te.columns if not c.startswith("emb_")]
    sc = te[keep].assign(skor=champ_score, skor_baseline=scores["Baseline bisnis"], model=champion,
                         # every candidate's raw test score, for paired bootstrap tests (graph ablation)
                         **{f"skor_{slug(n)}": s for n, s in scores.items() if n != "Baseline bisnis"})
    sc["peringkat"] = sc["skor"].rank(ascending=False, method="first").astype(int)
    if "tipe_perusahaan" in sc:   # acquisition: RM lists rank prospects within their type
        tipe = np.select([sc.get("peran_pedagang", 0) == 1, sc.get("peran_karyawan", 0) == 1, sc["tipe_perusahaan"] == 1],
                         ["pedagang", "karyawan", "perusahaan"], "lainnya")
        sc["tipe_prospek"] = tipe
        sc["peringkat_dalam_tipe"] = sc.groupby("tipe_prospek")["skor"].rank(ascending=False, method="first").astype(int)
    sc.to_parquet(sdir / f"{engine}_test.parquet", index=False)
    return {"tabel": result, "champion": champion, "params": best}
