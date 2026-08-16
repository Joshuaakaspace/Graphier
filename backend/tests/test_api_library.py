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


def test_style_presets_and_custom(session):
    mpl = pytest.importorskip("matplotlib")
    mpl.use("Agg")

    ax = session.plot_graph(style="dark")
    assert ax.figure.get_facecolor()[:3] != (1.0, 1.0, 1.0)  # not white

    custom = graphier.PlotStyle(background="#101418", colors={"PERSON": "#ffb86b"})
    ax2 = session.plot_timeline(style=custom)
    assert ax2.figure.get_facecolor()[0] < 0.2  # dark custom background

    with pytest.raises(ValueError, match="unknown style"):
        session.plot_graph(style="vaporwave")


def test_focus_and_highlight_effects(session):
    mpl = pytest.importorskip("matplotlib")
    mpl.use("Agg")

    ax = session.plot_graph(focus="Acme Corp")
    assert "Acme Corp" in ax.get_title(loc="left")

    with pytest.raises(ValueError, match="focus entity"):
        session.plot_graph(focus="Nonexistent Corp")

    ax2 = session.plot_timeline(highlight="Ada Lovelace")
    bold = [t for t in ax2.get_yticklabels() if t.get_fontweight() == "bold"]
    assert len(bold) == 1 and "Ada Lovelace" in bold[0].get_text()
