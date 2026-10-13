"""Interactive, read-only cluster explorer; observed inventory and configured roles stay separate."""

import json
from pathlib import Path

import streamlit as st

ASSETS = Path(__file__).parent / "assets"


def render_cluster(cluster: dict, health: dict, workload: dict, palette: dict, links: dict) -> None:
    """Send inventory as data, never executable HTML; interactions run locally."""
    component = st.components.v2.component(
        "cluster_explorer",
        html='<div class="cluster-explorer"></div>',
        css=(ASSETS / "cluster.css").read_text(),
        js=(ASSETS / "cluster.js").read_text(),
    )
    component(
        key="cluster-explorer",
        data={
            "cluster": cluster,
            "health": health,
            "workload": workload,
            "palette": palette,
            "links": links,
            "catalog": json.loads((ASSETS / "cluster-catalog.json").read_text()),
        },
        height="content",
    )
