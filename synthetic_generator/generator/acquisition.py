"""Acquisition labels: which non-customers in the value chain become Bank customers in
the label window (months after `bulan_fitur_terakhir`).

The label comes from a known formula (Guideline Data Sintetis, section 6). Features use
only months up to `bulan_fitur_terakhir`, so nothing from the label window leaks in.
Coefficients live in config.yaml (akuisisi) and stay hidden from the model builder.
"""
import numpy as np
import pandas as pd
from scipy import sparse
from scipy.special import expit

from .products import primary_product

SCALE_RANK = {"Perorangan": 0, "Mikro": 0, "Kecil": 1, "Menengah": 2, "Besar": 3}


def build(ref, comp: pd.DataFrame, persons: pd.DataFrame, emp: pd.DataFrame,
          truth: pd.DataFrame, transfers: pd.DataFrame, rng: np.random.Generator):
    cfg, T = ref.cfg["akuisisi"], ref.cfg["bulan"]
    last = cfg["bulan_fitur_terakhir"]
    coef = cfg["koefisien"]

    sector_of_company = comp.set_index("company_id")["sektor"]
    employer = emp.drop_duplicates("person_id").set_index("person_id")["company_id"]
    ent = pd.concat([
        pd.DataFrame({"entity_id": comp["company_id"], "tipe": "PERUSAHAAN", "is_bank": comp["is_bank_customer"],
                      "skala": comp["skala"], "sektor": comp["sektor"], "is_anchor": comp["is_anchor"],
                      "omzet_tahunan_rp": comp["omzet_tahunan_rp"]}),
        pd.DataFrame({"entity_id": persons["person_id"], "tipe": "PERORANGAN", "is_bank": persons["is_bank_customer"],
                      "skala": "Perorangan", "sektor": persons["person_id"].map(employer).map(sector_of_company),
                      "is_anchor": False, "omzet_tahunan_rp": np.nan}),
    ], ignore_index=True)
    pos = pd.Series(np.arange(len(ent)), index=ent["entity_id"])
    is_bank = ent["is_bank"].to_numpy().astype(bool)

    # The label follows the true world (all transfers, true scale): whether someone
    # switches bank depends on things the bank cannot see. Model features must only use
    # what the bank can see: transfers with at least one Bank side.
    sectors = ent["sektor"].fillna("NA")
    sector_effect = sectors.map(pd.Series(rng.normal(0, coef["sektor"], sectors.nunique()), index=sectors.unique())).to_numpy()
    noise = rng.normal(0, cfg["noise_sd"], len(ent))
    visible = visible_transfers(ent, transfers)
    candidate = ~is_bank
    joined = np.zeros(len(ent), dtype=int)
    feats, seen = [], set()

    # Walk-forward: each window has its own feature cut-off and label months; the base rate
    # is calibrated per window among candidates that have not joined yet.
    for w_last, w_end in cfg["jendela_label"]:
        f, _ = graph_features(ent, pos, is_bank, transfers, w_last)
        f["skala"] = ent["skala"].map(SCALE_RANK).to_numpy()
        z = (f - f.mean()) / f.std().replace(0, 1)
        terms = ["log_nominal_dengan_bank", "porsi_tetangga_bank", "lama_relasi_bulan", "porsi_bank_dua_langkah", "skala"]
        coef_c = {**coef, **cfg.get("koefisien_perusahaan", {})}
        base_all = sum(coef[c] * z[c].to_numpy() for c in terms)
        base_comp = sum(coef_c[c] * z[c].to_numpy() for c in terms)
        base = np.where(ent["tipe"].to_numpy() == "PERUSAHAAN", base_comp, base_all) + sector_effect + noise
        vf, ve = graph_features(ent, pos, is_bank, visible, w_last)
        vf["sektor"] = ent["sektor"].fillna("NA").to_numpy()
        feats.append(vf.assign(bulan_fitur_terakhir=w_last))
        if w_last == last:
            seen, visible_e = set(ve["src"]), ve

        # Neighbours for the contagion term: any relation that started inside the feature window.
        known = truth[(truth["bulan_mulai"] <= w_last) & truth["from_id"].isin(pos.index) & truth["to_id"].isin(pos.index)]
        a, b = pos[known["from_id"]].to_numpy(), pos[known["to_id"]].to_numpy()
        adj = sparse.coo_matrix((np.ones(2 * len(a)), (np.r_[a, b], np.r_[b, a])), shape=(len(ent), len(ent))).tocsr()
        open_ = candidate & (joined == 0)
        window = list(range(w_last + 1, w_end + 1))
        draws = rng.random((len(window), len(ent)))          # common random numbers for calibration

        def simulate(b0):
            got = joined.copy()
            for k, t in enumerate(window):
                recent = (got == t - 1) & (got > 0)
                contagion = (adj @ recent.astype(float)) > 0
                h = expit(b0 + base + coef["tetangga_baru_bergabung"] * contagion)
                new = open_ & (got == 0) & (draws[k] < h)
                got[new] = t
            return got

        lo, hi = -15.0, 5.0
        for _ in range(40):  # bisection on the intercept to hit the target base rate
            mid = (lo + hi) / 2
            rate = (simulate(mid)[open_] > 0).mean()
            lo, hi = (mid, hi) if rate < cfg["base_rate_target"] else (lo, mid)
        joined = simulate((lo + hi) / 2)

    out = ent[candidate][["entity_id", "tipe", "skala"]].copy()
    out["terlihat_bank"] = out["entity_id"].isin(seen).astype(np.int8)
    out["bulan_jadi_nasabah"] = joined[candidate]
    windows = cfg["jendela_label"]
    out["jendela"] = np.select([out["bulan_jadi_nasabah"].between(a + 1, b) for a, b in windows],
                               list(range(1, len(windows) + 1)), 0)
    month_start = ref.calendar.set_index("bulan_ke")["bulan"]
    days = rng.integers(0, 28, len(out))
    out["tanggal_jadi_nasabah"] = [
        (pd.Timestamp(month_start[m]) + pd.Timedelta(days=int(d))).date().isoformat() if m > 0 else ""
        for m, d in zip(out["bulan_jadi_nasabah"], days)
    ]
    out["produk_pertama"] = first_product(ref, out, persons, emp)
    out.loc[out["bulan_jadi_nasabah"] == 0, "produk_pertama"] = ""
    out["via_anchor_id"] = out["entity_id"].map(via_anchor(visible_e, comp)).fillna("")
    out.loc[out["bulan_jadi_nasabah"] == 0, "via_anchor_id"] = ""
    return out.drop(columns="skala").reset_index(drop=True), pd.concat(feats).rename_axis("entity_id").reset_index()


def visible_transfers(ent: pd.DataFrame, transfers: pd.DataFrame) -> pd.DataFrame:
    """Bank only sees a transfer when at least one side holds an account at Bank."""
    own_cust = set(ent.loc[ent["is_bank"].astype(bool), "entity_id"])
    return transfers[transfers["from_id"].isin(own_cust) | transfers["to_id"].isin(own_cust)]


def graph_features(ent: pd.DataFrame, pos: pd.Series, is_bank: np.ndarray, transfers: pd.DataFrame, last: int):
    """Per entity, from the feature window: money exchanged with Bank entities, share of
    counterparties at Bank, and number of months with a Bank counterparty."""
    tw = transfers[transfers["bulan_ke"] <= last]
    e = pd.concat([tw.rename(columns={"from_id": "src", "to_id": "dst"}),
                   tw.rename(columns={"to_id": "src", "from_id": "dst"})], ignore_index=True)
    e = e[e["src"].isin(pos.index) & e["dst"].isin(pos.index)]
    e["dst_bank"] = is_bank[pos[e["dst"]].to_numpy()]
    nominal_bank = e[e["dst_bank"]].groupby("src")["total_nominal_rp"].sum()
    share_bank = e.drop_duplicates(["src", "dst"]).groupby("src")["dst_bank"].mean()
    months_bank = e[e["dst_bank"]].groupby("src")["bulan_ke"].nunique()
    f = pd.DataFrame(index=ent["entity_id"])
    f["log_nominal_dengan_bank"] = np.log1p(nominal_bank.reindex(f.index).fillna(0))
    f["porsi_tetangga_bank"] = share_bank.reindex(f.index).fillna(0)
    f["lama_relasi_bulan"] = months_bank.reindex(f.index).fillna(0)
    f["porsi_bank_dua_langkah"] = two_step_share(pos, is_bank, e)
    return f, e


def two_step_share(pos: pd.Series, is_bank: np.ndarray, e: pd.DataFrame) -> np.ndarray:
    """Share of Bank accounts among the neighbours of my neighbours (excluding me): for an
    employee, colleagues paid by the same employer; for a supplier, the anchor's other
    partners. A bank sees this from the recipient list of transfers it processes."""
    pairs = e.drop_duplicates(["src", "dst"])
    i, j = pos[pairs["src"]].to_numpy(), pos[pairs["dst"]].to_numpy()
    n = len(pos)
    adj = sparse.csr_matrix((np.ones(len(i)), (i, j)), shape=(n, n))
    deg = np.asarray(adj.sum(axis=1)).ravel()
    bank_nbrs = adj @ is_bank.astype(float)
    # Two-step paths through each neighbour k, minus the path that comes straight back.
    paths = adj @ deg - deg
    bank_paths = adj @ bank_nbrs - deg * is_bank
    return np.where(paths > 0, bank_paths / np.maximum(paths, 1), 0.0)


def first_product(ref, out: pd.DataFrame, persons: pd.DataFrame, emp: pd.DataFrame) -> np.ndarray:
    """Catalog rules: unincorporated micro/small firms, business owners and traders -> Tabungan Plus
    Bisnis; medium/large firms -> Giro (Non Perorangan); employees -> their primary savings account."""
    owners = set(emp.loc[emp["peran"].isin(["PEMILIK", "PEMBELI"]), "person_id"])
    p = persons.set_index("person_id")
    res = []
    for r in out.itertuples():
        if r.tipe == "PERUSAHAAN":
            res.append("Tabungan Plus Bisnis" if r.skala in ("Mikro", "Kecil") else "Bank Giro (Non Perorangan)")
        elif r.entity_id in owners:
            res.append("Tabungan Plus Bisnis")
        else:
            age, occ = p.at[r.entity_id, "usia"], p.at[r.entity_id, "pekerjaan"]
            res.append(primary_product(np.array([age]), np.array([occ]), ref.cfg["nasabah"])[0])
    return np.array(res)


def via_anchor(e: pd.DataFrame, comp: pd.DataFrame) -> pd.Series:
    """The anchor the entity exchanged the most money with in the feature window."""
    anchors = set(comp.loc[comp["is_anchor"], "company_id"])
    ea = e[e["dst"].isin(anchors)].groupby(["src", "dst"])["total_nominal_rp"].sum().reset_index()
    return ea.sort_values("total_nominal_rp").drop_duplicates("src", keep="last").set_index("src")["dst"]
