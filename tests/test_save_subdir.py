import pandas as pd

from scraper import clean, save


def test_save_crea_subdirectorio_si_no_existe(tmp_path):
    df = clean([
        {
            "title": "Libro Demo",
            "price": "£1,299.50",
            "rating": "Five",
            "in_stock": True,
            "url": "https://books.toscrape.com/a",
        }
    ])
    prefix = tmp_path / "salida" / "reporte"
    xlsx, csv = save(df, str(prefix))
    assert (tmp_path / "salida" / "reporte.xlsx").exists()
    assert (tmp_path / "salida" / "reporte.csv").exists()
    assert pd.read_csv(csv).iloc[0]["price_gbp"] == 1299.50
