import pytest

import graphier
from graphier.demo import seed_demo
from graphier.vault import Vault


@pytest.fixture()
def session(tmp_path):
    seed_demo(Vault(str(tmp_path)))
    return graphier.open(tmp_path)


def test_data_access(session):
    people = session.entities("PERSON")
    assert any(e["text"] == "Ada Lovelace" for e in people)

    founded = session.relations("founded by")
    assert founded and founded[0]["evidence"][0]["sentence"]

    rows = session.query("?- empire_builder(P, B)")
    assert {"P": "Ada Lovelace", "B": "Widget Inc"} in rows

    page = session.entity("Acme Corp")
    assert page and any("founded Acme Corp" in m["sentence"] for m in page["mentions"])

    assert session.conflicts() and session.timeline()


def test_to_networkx(session):
    g = session.to_networkx()
    assert g.has_node("Ada Lovelace")
    data = g.get_edge_data("Acme Corp", "Ada Lovelace")
    assert data and data["predicate"] == "founded_by" and data["evidence"]


def test_plots_return_axes(session):
    mpl = pytest.importorskip("matplotlib")
    mpl.use("Agg")

    ax = session.plot_graph()
    assert ax.has_data() or len(ax.collections) > 0

    ax2 = session.plot_timeline()
    assert len(ax2.collections) > 0  # lifeline scatter marks
    labels = [t.get_text() for t in ax2.get_yticklabels()]
    assert any("Ada Lovelace" in l for l in labels)


def test_plot_without_matplotlib_message(session, monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name.startswith("matplotlib"):
            raise ImportError("nope")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(ImportError, match=r"graphier\[viz\]"):
        session.plot_graph()
