"""
============================================================
  Item sprite labeller

  Walk through every blob extracted by extract_item_blobs.py
  and assign a SpriteName from AutoItemMapping.json. The
  result is written to data/items/labels.json AND a copy of
  the labelled crop is saved to data/items/<SpriteName>.png
  so identify_item() can load it with no extra plumbing.

  UI:

    * Top: large preview of the current blob
    * Side: dropdown of unassigned SpriteNames for the current
      age (filtered, click to assign)
    * Bottom: progress bar + "Skip" / "Save" buttons

  Keyboard:

    n / →   next blob
    p / ←   previous blob
    Space   skip without assigning
    s       save labels.json now
    q       quit (auto-saves)

  Re-runnable: existing labels are loaded on startup, only
  unlabeled blobs are presented.
============================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import ttk, messagebox
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from data.libraries import DATA_DIR, AGE_TO_SPRITESHEET  # noqa: E402

log = logging.getLogger(__name__)

ITEMS_DIR  = DATA_DIR / "items"
RAW_DIR    = ITEMS_DIR / "raw"
LABELS_FN  = ITEMS_DIR / "labels.json"


# ────────────────────────────────────────────────────────────
#  Data plumbing
# ────────────────────────────────────────────────────────────


def _load_blobs() -> dict:
    manifest = RAW_DIR / "blobs.json"
    if not manifest.is_file():
        raise SystemExit(
            "data/items/raw/blobs.json missing — run "
            "tools/extract_item_blobs.py first"
        )
    return json.loads(manifest.read_text())


def _load_labels() -> dict:
    if LABELS_FN.is_file():
        return json.loads(LABELS_FN.read_text())
    return {"labels": {}}


def _load_auto_mapping() -> dict:
    return json.loads((DATA_DIR / "AutoItemMapping.json").read_text())


def _save_labels(labels: dict) -> None:
    ITEMS_DIR.mkdir(parents=True, exist_ok=True)
    LABELS_FN.write_text(json.dumps(labels, indent=2))


def _items_for_age(auto: dict, age: int) -> List[dict]:
    return [v for v in auto.values() if v.get("Age") == age]


# ────────────────────────────────────────────────────────────
#  GUI
# ────────────────────────────────────────────────────────────


class LabelApp:

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Label item sprites")

        self.blobs    = _load_blobs()
        self.auto     = _load_auto_mapping()
        self.labels   = _load_labels()

        # Flat queue of (age, blob_meta) pairs filtered to unlabelled.
        self.queue: List[Tuple[int, dict]] = []
        labelled_files = {l["filename"] for l in self.labels.get("labels", {}).values()
                          if isinstance(l, dict) and l.get("filename")}
        for age_str, sheet_meta in self.blobs.items():
            age = int(age_str)
            for b in sheet_meta["blobs"]:
                # Heuristic: the user copies the labelled crop to
                # data/items/<SpriteName>.png; if a label entry already
                # references the source filename, skip.
                src = b["filename"]
                if any(src == lab.get("source_filename")
                       for lab in self.labels.get("labels", {}).values()
                       if isinstance(lab, dict)):
                    continue
                self.queue.append((age, b))
        self.cursor = 0

        # ── widgets ─────────────────────────────────────────
        top = tk.Frame(root, padx=8, pady=8)
        top.pack(fill="both", expand=True)

        self.preview_lbl = tk.Label(top, bg="#222", width=320, height=320)
        self.preview_lbl.pack(side="left", padx=(0, 12))

        side = tk.Frame(top)
        side.pack(side="right", fill="y")

        self.title_lbl = tk.Label(side, text="", font=("Arial", 11, "bold"))
        self.title_lbl.pack(anchor="w")
        self.meta_lbl  = tk.Label(side, text="", font=("Arial", 9), fg="#666",
                                  justify="left")
        self.meta_lbl.pack(anchor="w", pady=(0, 8))

        tk.Label(side, text="Filter:", font=("Arial", 9)).pack(anchor="w")
        self.filter_var = tk.StringVar()
        self.filter_var.trace_add("write", lambda *_: self._refresh_dropdown())
        tk.Entry(side, textvariable=self.filter_var, width=30).pack(
            anchor="w", pady=(0, 4))

        tk.Label(side, text="Unassigned items for this age:",
                 font=("Arial", 9)).pack(anchor="w")
        self.dropdown = tk.Listbox(side, width=42, height=20)
        self.dropdown.pack(fill="y", expand=True)
        self.dropdown.bind("<Double-Button-1>", lambda e: self._assign())

        btn_frame = tk.Frame(side)
        btn_frame.pack(fill="x", pady=(8, 0))
        tk.Button(btn_frame, text="Assign (Enter)",
                  command=self._assign).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Skip (Space)",
                  command=self._next).pack(side="left", padx=2)
        tk.Button(btn_frame, text="Save",
                  command=self._save).pack(side="left", padx=2)

        nav_frame = tk.Frame(side)
        nav_frame.pack(fill="x", pady=(4, 0))
        tk.Button(nav_frame, text="← Prev", command=self._prev).pack(side="left")
        tk.Button(nav_frame, text="Next →", command=self._next).pack(side="left", padx=8)

        self.progress_lbl = tk.Label(side, text="", font=("Arial", 9), fg="#0a0")
        self.progress_lbl.pack(anchor="w", pady=(8, 0))

        # Bindings
        root.bind("<Return>",    lambda e: self._assign())
        root.bind("<space>",     lambda e: self._next())
        root.bind("<n>",         lambda e: self._next())
        root.bind("<Right>",     lambda e: self._next())
        root.bind("<p>",         lambda e: self._prev())
        root.bind("<Left>",      lambda e: self._prev())
        root.bind("<s>",         lambda e: self._save())
        root.bind("<q>",         lambda e: self._quit())
        root.protocol("WM_DELETE_WINDOW", self._quit)

        if not self.queue:
            messagebox.showinfo(
                "Done",
                "No unlabelled blobs left. Re-run extract_item_blobs.py "
                "if you want to start over.",
            )
            root.destroy()
            return

        self._show_current()

    # ── per-blob view ───────────────────────────────────────

    def _show_current(self) -> None:
        if not self.queue:
            return
        age, blob = self.queue[self.cursor]
        sheet_meta = self.blobs[str(age)]
        crop_path = RAW_DIR / blob["filename"]
        img = Image.open(crop_path).convert("RGBA")
        # Fit to ~280×280
        scale = min(280 / img.width, 280 / img.height, 4.0)
        disp = img.resize((int(img.width * scale), int(img.height * scale)),
                          Image.NEAREST)
        self._photo = ImageTk.PhotoImage(disp)
        self.preview_lbl.configure(image=self._photo, width=disp.width, height=disp.height)
        self.title_lbl.configure(
            text=f"Age {age} ({sheet_meta['spritesheet']}) — {blob['filename']}"
        )
        self.meta_lbl.configure(text=f"bbox = {blob['bbox']}")
        self._refresh_dropdown()
        self.progress_lbl.configure(
            text=f"{self.cursor + 1} / {len(self.queue)}  "
                 f"({len(self.labels.get('labels', {}))} labelled)"
        )

    def _refresh_dropdown(self) -> None:
        if not self.queue:
            return
        age, _ = self.queue[self.cursor]
        items = _items_for_age(self.auto, age)
        assigned = {l["SpriteName"] for l in self.labels.get("labels", {}).values()
                    if isinstance(l, dict) and "SpriteName" in l}
        candidates = [
            it for it in items
            if it["SpriteName"] not in assigned
        ]
        flt = self.filter_var.get().lower().strip()
        if flt:
            candidates = [it for it in candidates
                          if flt in it["SpriteName"].lower()
                          or flt in it.get("ItemName", "").lower()
                          or flt in it.get("TypeName", "").lower()]

        self.dropdown.delete(0, "end")
        self._dropdown_data = candidates
        for it in candidates:
            self.dropdown.insert(
                "end",
                f"{it['SpriteName']:40s}  ({it['TypeName']}, Idx={it['Idx']})",
            )

    # ── actions ─────────────────────────────────────────────

    def _assign(self) -> None:
        sel = self.dropdown.curselection()
        if not sel:
            self.progress_lbl.configure(text="Select an item in the list first.")
            return
        item = self._dropdown_data[sel[0]]
        age, blob = self.queue[self.cursor]

        # Save the cropped sprite under data/items/<SpriteName>.png so
        # identify_item can grab it directly.
        ITEMS_DIR.mkdir(parents=True, exist_ok=True)
        src = RAW_DIR / blob["filename"]
        dst = ITEMS_DIR / f"{item['SpriteName']}.png"
        Image.open(src).save(dst)

        self.labels.setdefault("labels", {})[item["SpriteName"]] = {
            "SpriteName":      item["SpriteName"],
            "Age":             item["Age"],
            "Type":            item["Type"],
            "Idx":             item["Idx"],
            "filename":        f"{item['SpriteName']}.png",
            "source_filename": blob["filename"],
            "source_age":      age,
            "source_bbox":     blob["bbox"],
        }
        _save_labels(self.labels)
        self._next()

    def _next(self) -> None:
        if self.cursor < len(self.queue) - 1:
            self.cursor += 1
            self._show_current()

    def _prev(self) -> None:
        if self.cursor > 0:
            self.cursor -= 1
            self._show_current()

    def _save(self) -> None:
        _save_labels(self.labels)
        messagebox.showinfo("Saved", f"Wrote {LABELS_FN}")

    def _quit(self) -> None:
        _save_labels(self.labels)
        self.root.destroy()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("-v", "--verbose", action="count", default=0)
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING - 10 * min(args.verbose, 2),
        format="%(asctime)s %(levelname)-7s %(message)s",
    )

    root = tk.Tk()
    LabelApp(root)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
