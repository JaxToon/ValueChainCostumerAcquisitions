"""Generate every synthetic dataset the capstone needs, then validate it.

    python run.py                    # full size from config.yaml
    python run.py --nasabah 5000     # quick run
"""
import argparse
import time
from pathlib import Path

import numpy as np
import yaml

from generator import acquisition, customers, export, validate, wholesale
from generator import ref as R
from generator import value_chain as V

HERE = Path(__file__).resolve().parent


def main():
    ap = argparse.ArgumentParser(description="Generator data sintetis capstone NBO + value chain")
    ap.add_argument("--config", default=HERE / "config.yaml", type=Path)
    ap.add_argument("--out", default=HERE / "output", type=Path)
    ap.add_argument("--nasabah", type=int, help="override nasabah.jumlah_awal")
    args = ap.parse_args()

    ref = R.load(args.config)
    if args.nasabah:
        ref.cfg["nasabah"]["jumlah_awal"] = args.nasabah
    rng = np.random.default_rng(ref.cfg["seed"])
    out = args.out
    out.mkdir(parents=True, exist_ok=True)
    start = time.time()

    print("1/6 nasabah dan produk bulanan")
    pop, cust, panel, levels = customers.build(ref, rng)
    print("2/6 perusahaan dan relasi")
    comp = V.build_companies(ref, rng)
    rel = V.build_relations(ref, comp, rng)
    print("3/6 karyawan, pemilik, dan transfer")
    persons, emp = V.build_people(ref, comp, pop, cust, panel, rng)
    transfers = V.build_transfers(ref, comp, rel, emp, persons, rng)
    truth = V.relationship_truth(rel, emp)
    print("4/6 label akuisisi")
    acq, feats = acquisition.build(ref, comp, persons, emp, truth, transfers, rng)

    print("5/6 lapisan wholesale (RM, transaksi counterparty, produk, fasilitas, lead)")
    ws = wholesale.build(ref, comp, rel, transfers, rng)
    comp = ws["companies"]

    print("6/6 menulis file dan validasi")
    panel.insert(2, "bulan", panel["bulan_ke"].map(ref.calendar.set_index("bulan_ke")["bulan"]))
    data = {"population": pop, "customers": cust, "panel": panel, "levels": levels, "companies": comp,
            "relations": rel, "persons": persons, "employment": emp, "transfers": transfers,
            "acquisitions": acq, "features": feats, "wholesale": ws}
    # data_bank/ = what a bank could really see; kunci_evaluasi/ = full truth (kamus_data.csv)
    data["data_bank"] = export.write(out, data, {"relationship_truth.csv": truth}, ref.cfg.get("data_kotor", {}), rng)
    (out / "config_terpakai.yaml").write_text(yaml.safe_dump(ref.cfg, allow_unicode=True, sort_keys=False), encoding="utf-8")

    report = validate.run(ref, data)
    (out / "validation_report.md").write_text("\n".join(report.lines), encoding="utf-8")

    print(f"Selesai dalam {time.time() - start:.0f} detik -> {out}")
    print(f"Nasabah {cust.shape[0]:,} | baris bulanan {panel.shape[0]:,} | perusahaan {comp.shape[0]:,} | "
          f"persons {persons.shape[0]:,} | transfer {transfers.shape[0]:,} | kandidat akuisisi {acq.shape[0]:,}")
    print(f"Wholesale: RM {ws['rm_portofolio']['rm_id'].nunique()} | baris transaksi counterparty {len(ws['transaksi']):,} | "
          f"riwayat produk {len(ws['riwayat_produk']):,} | fasilitas {len(ws['fasilitas']):,} | lead Bisdev {len(ws['lead_bisdev']):,}")
    if report.fails:
        print("Validasi GAGAL untuk: " + "; ".join(report.fails))
    else:
        print("Semua cek validasi LOLOS")


if __name__ == "__main__":
    main()
