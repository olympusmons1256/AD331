"""Exercise the Streamlit entry point as a script, including both UI actions."""

from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_streamlit_app_search_and_benchmark() -> None:
    app_path = Path(__file__).resolve().parents[1] / "src" / "app.py"
    app = AppTest.from_file(str(app_path), default_timeout=60).run()
    assert not app.exception

    app.button[0].click().run(timeout=60)
    assert not app.exception
    assert any("BM25 Keyword Search" in heading.value for heading in app.subheader)

    app.button[1].click().run(timeout=60)
    assert not app.exception
    assert len(app.dataframe) >= 1
