"""Split the generated world into what a bank could really see (data_bank/) and the full
truth kept only for evaluation (kunci_evaluasi/). The rules follow kamus_data.csv."""
import shutil
from pathlib import Path

import numpy as np
import pandas as pd

from . import dirty
from .acquisition import visible_transfers
from .people import income_band

HERE = Path(__file__).resolve().parents[1]
HIDDEN_COMPANY = ["skala", "omzet_tahunan_rp", "jumlah_karyawan", "peran", "bank_payroll", "segmen_bank"]
# Truth-only helpers from the wholesale layer, never in data_bank.
WHOLESALE_TRUTH = ["punya_rekening_bank_lain", "punya_beberapa_rekening_bank", "bank_lain_sendiri"]
HIDDEN_PERSON = ["usia", "jenis_kelamin", "provinsi", "perkotaan", "pekerjaan", "kisaran_pendapatan"]


def income_range(income: pd.Series) -> pd.Series:
    return income_band(income).replace({"Tidak ada kegiatan ekonomi": "Tidak ada penghasilan sendiri"}).to_numpy()


def bank_view(d: dict) -> dict:
    cust, persons, comp, emp, tr, acq = (d[k] for k in ["customers", "persons", "companies", "employment", "transfers", "acquisitions"])
    ent = pd.concat([pd.DataFrame({"entity_id": comp["company_id"], "is_bank": comp["is_bank_customer"]}),
                     pd.DataFrame({"entity_id": persons["person_id"], "is_bank": persons["is_bank_customer"]})])
    tr_v = visible_transfers(ent, tr)
    seen = set(tr_v["from_id"]) | set(tr_v["to_id"])

    nasabah = cust.drop(columns="pendapatan_bulanan_idr").assign(kisaran_pendapatan=income_range(cust["pendapatan_bulanan_idr"]))

    c = comp[(comp["is_bank_customer"] == 1) | comp["company_id"].isin(seen)].drop(columns=WHOLESALE_TRUTH, errors="ignore")
    c[HIDDEN_COMPANY] = c[HIDDEN_COMPANY].astype(object)
    c.loc[c["is_bank_customer"] == 0, HIDDEN_COMPANY] = np.nan

    p = persons[(persons["is_bank_customer"] == 1) | persons["person_id"].isin(seen)].copy()
    p["kisaran_pendapatan"] = income_range(p["pendapatan_bulanan_idr"])
    p = p.drop(columns=["pendapatan_bulanan_idr", "bank_payroll"])
    p[HIDDEN_PERSON] = p[HIDDEN_PERSON].astype(object)
    p.loc[p["is_bank_customer"] == 0, HIDDEN_PERSON] = np.nan

    bank_company = set(comp.loc[comp["is_bank_customer"] == 1, "company_id"])
    customer = set(persons.loc[persons["is_bank_customer"] == 1, "person_id"])
    paid_seen = set(zip(tr_v["from_id"], tr_v["to_id"]))
    seen_pair = [(c_, p_) in paid_seen or (p_, c_) in paid_seen for c_, p_ in zip(emp["company_id"], emp["person_id"])]
    keep = np.where(emp["peran"] == "PEMILIK", emp["company_id"].isin(bank_company),
                    emp["person_id"].isin(customer).to_numpy() | np.array(seen_pair))

    ws = d["wholesale"]
    return {
        "nasabah.csv": nasabah,
        "nasabah_bulanan.parquet": d["panel"],
        "produk_level.csv": d["levels"],
        "companies.csv": c,
        "persons.csv": p,
        "employment.csv": emp[keep],
        "transfers_monthly.csv": tr_v,
        "acquisitions.csv": acq[acq["terlihat_bank"] == 1].drop(columns="terlihat_bank"),
        "rm_portofolio.csv": ws["rm_portofolio"],
        "transaksi_counterparty_bulanan.csv": ws["transaksi"],
        "saldo_bulanan.csv": ws["saldo"],
        "riwayat_produk_wholesale.csv": ws["riwayat_produk"],
        "fasilitas_pembiayaan.csv": ws["fasilitas"],
        "lead_bisdev.csv": ws["lead_bisdev"],
        "label_wholesale.csv": ws["label"],
    }


def write(out: Path, d: dict, truth_extra: dict, dirty_cfg: dict, rng) -> dict:
    bank, key = out / "data_bank", out / "kunci_evaluasi"
    for folder in (bank, key):
        shutil.rmtree(folder, ignore_errors=True)
        folder.mkdir(parents=True)
    clean = bank_view(d)
    view, dirt_log = dirty.apply(clean, dirty_cfg, rng)
    if len(dirt_log):
        dirt_log.to_csv(key / "catatan_data_kotor.csv", index=False)
    d["data_bank_bersih"], d["catatan_data_kotor"] = clean, dirt_log
    for name, df in view.items():
        if name.endswith(".parquet"):
            df.to_parquet(bank / name, index=False)
        else:
            df.to_csv(bank / name, index=False)
    shutil.copy(HERE / "kamus_data.csv", bank / "kamus_data.csv")

    full = {"nasabah_lengkap.csv": d["customers"], "persons_lengkap.csv": d["persons"],
            "companies_lengkap.csv": d["companies"], "employment_lengkap.csv": d["employment"],
            "transfers_lengkap.csv": d["transfers"], "acquisitions_lengkap.csv": d["acquisitions"],
            "lead_bisdev_kunci.csv": d["wholesale"]["lead_bisdev_kunci"],
            "counterparty_pindah_bank.csv": d["wholesale"]["pindah_bank"], **truth_extra}
    for name, df in full.items():
        df.to_csv(key / name, index=False)
    return view
