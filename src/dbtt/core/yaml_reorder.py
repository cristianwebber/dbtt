"""Alphabetically reorder the ``models:`` in a dbt schema file.

Ported from the original pyyaml-based ``yml-fix``, but built on ruamel so
comments and formatting survive. The subtlety is that ruamel stores comments
that sit *between* sequence items in the parent sequence keyed by item index;
naively reordering the Python list would leave those comments behind on the
wrong items. :func:`_sort_commented_seq` remaps them so each comment follows its
item. Comments written inside an item's mapping (e.g. an end-of-line comment on
a ``name:`` key) already live on that mapping and move with it for free.
"""

from __future__ import annotations

from typing import Any, Callable


def _model_key(item: Any) -> tuple[int, str]:
    # Named models sort alphabetically; anything without a name sorts last while
    # keeping its relative order (Python's sort is stable).
    if isinstance(item, dict) and item.get("name") is not None:
        return (0, str(item["name"]))
    return (1, "")


def _sort_commented_seq(seq: list, key: Callable[[Any], Any]) -> None:
    """Sort ``seq`` in place, carrying ruamel item-comments to new positions."""
    order = sorted(range(len(seq)), key=lambda i: key(seq[i]))
    if order == list(range(len(seq))):
        return

    new_elements = [seq[i] for i in order]

    ca_items = getattr(getattr(seq, "ca", None), "items", None)
    remapped = None
    if isinstance(ca_items, dict) and ca_items:
        old = dict(ca_items)
        remapped = {
            new_idx: old[old_idx]
            for new_idx, old_idx in enumerate(order)
            if old_idx in old
        }

    seq[:] = new_elements
    if remapped is not None:
        ca_items.clear()
        ca_items.update(remapped)


def reorder_models(doc: Any) -> bool:
    """Sort ``doc['models']`` by name in place. Returns True if the order changed."""
    if not isinstance(doc, dict):
        return False
    models = doc.get("models")
    if not isinstance(models, list) or len(models) < 2:
        return False

    before = [_model_key(m) for m in models]
    _sort_commented_seq(models, _model_key)
    after = [_model_key(m) for m in models]
    return before != after
