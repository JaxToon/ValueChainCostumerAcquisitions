"""Features of a window must not change when data after its feature month is removed."""
import pandas as pd

from src.features import acq_features, wholesale_features


def _cut(monkeypatch, module, last):
    real = module.clean

    def cut(name):
        df = real(name)
        if "bulan_ke" in df.columns and name in ("transfers", "transaksi_counterparty", "saldo"):
            return df[df["bulan_ke"] <= last]
        return df

    monkeypatch.setattr(module, "clean", cut)


def test_akuisisi_jendela_1_tanpa_data_masa_depan(monkeypatch):
    full = acq_features.build_window(1, 5, 11)
    _cut(monkeypatch, acq_features, 5)
    cut = acq_features.build_window(1, 5, 11)
    cols = acq_features.TABLE[1:] + acq_features.GRAPH
    pd.testing.assert_frame_equal(full[cols].reset_index(drop=True), cut[cols].reset_index(drop=True))


def test_wholesale_jendela_1_tanpa_data_masa_depan(monkeypatch):
    full = wholesale_features.build_window(1, 5)
    _cut(monkeypatch, wholesale_features, 5)
    cut = wholesale_features.build_window(1, 5)
    cols = [c for c in wholesale_features.GRAPH if not c.startswith("mirip")] + ["log_saldo_rata2", "tren_saldo_3bln"]
    pd.testing.assert_frame_equal(full[cols].reset_index(drop=True), cut[cols].reset_index(drop=True))
