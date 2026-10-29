"""RAG over the Bank product catalog (216 rows): TF-IDF search, no vector database.
Every answer the LLM gives about a product must cite a row returned here (URL_Sumber)."""
from functools import lru_cache

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from src.config import ROOT, settings

FIELDS = ["Nama_Produk", "Kategori", "Sub_Kategori", "Fungsi_Manfaat", "Target_Nasabah", "Rekomendasikan_Jika", "Syarat_Umum"]
# Grill me Q21/Q26: subsidiaries and digital channels are not recommended, except these.
EXCLUDED_SEGMENTS = {"Anak Usaha (Bank Group)", "Digital & E-Banking", "API / Open Banking"}
KEEP_ANYWAY = {"Mobile Banking", "QRIS Bank", "EDC Bank"}


# Terms the default tokenizer splits or misses (single letters, word forms): mapped to the catalog's words.
SYNONYMS = {"l/c": "lc letter of credit", "importir": "impor", "eksportir": "ekspor", "skbdn": "skbdn surat kredit berdokumen",
            "bank garansi": "bank garansi jaminan", "jaminan pelaksanaan": "bank garansi jaminan pelaksanaan"}


def normalize(text: str) -> str:
    text = str(text).lower()
    for k, v in SYNONYMS.items():
        text = text.replace(k, v)
    return text


@lru_cache
def catalog() -> pd.DataFrame:
    c = pd.read_csv(ROOT / settings()["paths"]["catalog"])
    c["boleh_direkomendasikan"] = ~c["Segmen"].isin(EXCLUDED_SEGMENTS) | c["Nama_Produk"].isin(KEEP_ANYWAY)
    c["hanya_corporate_besar"] = c["Segmen"].eq("API / Open Banking")
    c["teks"] = c[FIELDS].fillna("").astype(str).agg(" ".join, axis=1).map(normalize)
    return c


@lru_cache
def _index():
    c = catalog()
    vec = TfidfVectorizer(ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    return vec, vec.fit_transform(c["teks"])


def search(query: str, k: int = 5, only_recommendable: bool = True) -> pd.DataFrame:
    vec, X = _index()
    c = catalog()
    sim = (X @ vec.transform([normalize(query)]).T).toarray().ravel()
    out = c.assign(skor_cari=sim)
    if only_recommendable:
        out = out[out["boleh_direkomendasikan"]]
    out = out[out["skor_cari"] > 0].sort_values("skor_cari", ascending=False).head(k)
    return out[["No", "Nama_Produk", "Segmen", "Kategori", "Fungsi_Manfaat", "Target_Nasabah", "Rekomendasikan_Jika",
                "Tidak_Cocok_Jika", "Syarat_Umum", "Perlu_Verifikasi", "URL_Sumber", "skor_cari"]]


def product(name: str) -> dict | None:
    c = catalog()
    hit = c[c["Nama_Produk"].str.casefold() == str(name).casefold()]
    return None if hit.empty else hit.iloc[0].to_dict()
