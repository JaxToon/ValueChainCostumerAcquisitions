"""Prepare the visit packs the demo will click, so they open instantly from the cache instead
of waiting 15-30 s for Gemma. Picks the same entities each page shows first.

    python -m pipelines.warm_demo          # needs Ollama running; about 5-8 minutes
"""
import time
import warnings

warnings.filterwarnings("ignore")   # Streamlit cache decorators warn outside `streamlit run`

from app.components import data as D  # noqa: E402
from src.genai import agent  # noqa: E402


def demo_entities(per_list: int = 3) -> list[str]:
    pf = D.portfolio()
    anchor = D.anchor_showcase()
    tx = D.load("clean", "transaksi_counterparty")
    partners = set(tx.loc[tx["counterparty_id"] == anchor, "company_id"])
    comm = pf[pf["segmen_bank"] == "Commercial"]
    rm = comm.assign(m=comm["company_id"].isin(partners)).groupby("rm_id")["m"].sum().idxmax()   # page 1 default
    mine = pf[pf["rm_id"] == rm].sort_values("skor_cross_sell_wholesale", ascending=False)
    ids = [anchor] + mine["company_id"].head(per_list).tolist() + D.leads_for(rm)["counterparty_id"].head(per_list).tolist()
    s = D.load("scores", "nbo_test")                                                            # page 2 default list
    ids += s.sort_values("skor", ascending=False).drop_duplicates("person_id")["person_id"].head(per_list).tolist()
    p = D.prospects()                                                                           # page 3, each type
    for tipe in ["perusahaan", "pedagang", "karyawan"]:
        ids += p[p["tipe_prospek"] == tipe].sort_values("peringkat_dalam_tipe")["entity_id"].head(per_list).tolist()
    return list(dict.fromkeys(ids))


def main():
    ids = demo_entities()
    print(f"{len(ids)} entitas demo")
    for e in ids:
        t = time.time()
        r = agent.run(e, "Persiapan demo")
        print(f"{e}: mode {r['mode']}, {time.time() - t:.0f} s, {len(r['paket'].get('peluang', []))} peluang", flush=True)


if __name__ == "__main__":
    main()
