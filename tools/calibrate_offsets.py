"""
============================================================
  Opponent capture offset calibrator

  Visual helper to refine backend/enemy_icon_offsets.py for
  one user's actual game UI. Workflow:

    1. Drop a representative opponent screenshot anywhere on
       disk (a file picker opens if you don't pass --image).
    2. The script displays the screenshot with the current
       default rectangles overlaid (label, slot name, slot
       index).
    3. Click + drag to redraw any rectangle. Right-click to
       reset one to its default. Press <s> to save.
    4. The result is written to data/opponent_offsets.json
       as RATIOS, so the same calibration scales across
       different capture sizes.

  Use --batch to skip the GUI and recompute the JSON from a
  raw text dump (one "<key>: x y w h" line per entry, ratios
  in 0..1).

  Requires Tk (ships with stdlib) and Pillow.
============================================================
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import Dict, List, Optional, Tuple

from PIL import Image, ImageTk

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scan.offsets.opponent import (  # noqa: E402
    EQUIPMENT_RATIOS, MOUNT_RATIO, PET_RATIOS, SKILL_RATIOS,
    SLOT_ORDER, BORDER_RATIOS, BG_RATIOS, write_overrides,
)

log = logging.getLogger(__name__)


# ────────────────────────────────────────────────────────────
#  Slot definitions for the GUI
# ────────────────────────────────────────────────────────────


def _initial_targets() -> Dict[str, List[Tuple[float, float, float, float]]]:
    return {
        "equipment": list(EQUIPMENT_RATIOS),
        "border":    list(BORDER_RATIOS),
        "bg":        list(BG_RATIOS),
        "mount":     [tuple(MOUNT_RATIO)],
        "pets":      list(PET_RATIOS),
        "skills":    list(SKILL_RATIOS),
    }


COLORS = {
    "equipment": "#4488ff",
    "border":    "#ffaa00",
    "bg":        "#ff66ff",
    "mount":     "#22cc44",
    "pets":      "#ff5555",
    "skills":    "#ffeb3b",
}


def _slot_label(group: str, idx: int) -> str:
    if group == "equipment":
        return f"{SLOT_ORDER[idx]}({idx})"
    if group == "border":
        return f"bord-{SLOT_ORDER[idx]}"
    if group == "bg":
        return f"fond-{SLOT_ORDER[idx]}"
    if group == "mount":
        return "Mount"
    if group == "pets":
        return f"Pet{idx + 1}"
    if group == "skills":
        return f"Skill{idx + 1}"
    return f"{group}-{idx}"


# ────────────────────────────────────────────────────────────
#  Tk app
# ────────────────────────────────────────────────────────────


class CalibratorApp:
    """Lightweight Tk overlay for interactive calibration."""

    def __init__(self, root: tk.Tk, image_path: Path) -> None:
        self.root = root
        self.root.title(f"Calibrate offsets — {image_path.name}")

        self.image = Image.open(image_path).convert("RGB")
        self.W, self.H = self.image.size

        # Scale to fit screen if too large.
        max_w, max_h = 900, 1100
        self.scale = min(max_w / self.W, max_h / self.H, 1.0)
        disp_w = int(self.W * self.scale)
        disp_h = int(self.H * self.scale)
        disp = self.image.resize((disp_w, disp_h))
        self._photo = ImageTk.PhotoImage(disp)

        self.canvas = tk.Canvas(root, width=disp_w, height=disp_h,
                                highlightthickness=0, bg="#222")
        self.canvas.pack(side="left")
        self.canvas.create_image(0, 0, anchor="nw", image=self._photo)

        # State
        self.targets = _initial_targets()
        self.defaults = _initial_targets()
        self.selected: Optional[Tuple[str, int]] = None
        self.drag_start: Optional[Tuple[int, int]] = None
        self.preview_id: Optional[int] = None
        self.rect_ids: Dict[Tuple[str, int], int] = {}

        # Side panel
        side = tk.Frame(root, padx=8, pady=8)
        side.pack(side="right", fill="y")

        tk.Label(side, text="Slot to redraw:", font=("Arial", 10, "bold")).pack(anchor="w")
        self.listbox = tk.Listbox(side, height=20, width=24)
        self.listbox.pack(fill="y", expand=True)
        self.listbox.bind("<<ListboxSelect>>", self._on_select_slot)

        for group, items in self.targets.items():
            for i in range(len(items)):
                self.listbox.insert("end", f"{group}: {_slot_label(group, i)}")

        tk.Button(side, text="Save (S)", command=self._save).pack(pady=(8, 2), fill="x")
        tk.Button(side, text="Reset selected (R)", command=self._reset_selected).pack(pady=2, fill="x")
        tk.Button(side, text="Quit (Q)", command=self.root.destroy).pack(pady=2, fill="x")
        self.status = tk.Label(side, text="", fg="#0a0", justify="left",
                               wraplength=180, font=("Arial", 9))
        self.status.pack(pady=(8, 0), fill="x")

        # Bindings
        self.canvas.bind("<ButtonPress-1>",   self._on_mouse_down)
        self.canvas.bind("<B1-Motion>",       self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Button-3>",        self._on_right_click)
        self.root.bind("<s>", lambda e: self._save())
        self.root.bind("<r>", lambda e: self._reset_selected())
        self.root.bind("<q>", lambda e: self.root.destroy())

        self._redraw_all()

    # ── ratio ↔ canvas pixels ────────────────────────────────

    def _ratio_to_canvas(self, r: Tuple[float, float, float, float]) -> Tuple[int, int, int, int]:
        x, y, w, h = r
        return (int(x * self.W * self.scale), int(y * self.H * self.scale),
                int((x + w) * self.W * self.scale), int((y + h) * self.H * self.scale))

    def _canvas_to_ratio(self, x0, y0, x1, y1) -> Tuple[float, float, float, float]:
        ix0 = min(x0, x1) / self.scale
        iy0 = min(y0, y1) / self.scale
        ix1 = max(x0, x1) / self.scale
        iy1 = max(y0, y1) / self.scale
        return (ix0 / self.W, iy0 / self.H,
                (ix1 - ix0) / self.W, (iy1 - iy0) / self.H)

    # ── rendering ────────────────────────────────────────────

    def _redraw_all(self) -> None:
        for rid in self.rect_ids.values():
            self.canvas.delete(rid)
        self.rect_ids.clear()
        for group, items in self.targets.items():
            colour = COLORS[group]
            for i, ratio in enumerate(items):
                x0, y0, x1, y1 = self._ratio_to_canvas(ratio)
                rid = self.canvas.create_rectangle(
                    x0, y0, x1, y1, outline=colour,
                    width=2 if (group, i) == self.selected else 1,
                )
                self.rect_ids[(group, i)] = rid

    # ── selection ────────────────────────────────────────────

    def _on_select_slot(self, _event=None) -> None:
        sel = self.listbox.curselection()
        if not sel:
            return
        line = self.listbox.get(sel[0])
        group, _, _ = line.partition(":")
        index = sel[0]
        # Recover (group, i) from listbox index.
        n_seen = 0
        for g, items in self.targets.items():
            for i in range(len(items)):
                if n_seen == index:
                    self.selected = (g, i)
                    self.status.config(
                        text=f"Selected: {g} #{i}\nDrag on the image to redraw."
                    )
                    self._redraw_all()
                    return
                n_seen += 1

    # ── mouse drag = redraw selected rect ───────────────────

    def _on_mouse_down(self, event) -> None:
        if self.selected is None:
            self.status.config(text="Pick a slot in the list first.")
            return
        self.drag_start = (event.x, event.y)
        if self.preview_id is not None:
            self.canvas.delete(self.preview_id)
        self.preview_id = self.canvas.create_rectangle(
            event.x, event.y, event.x, event.y,
            outline="#fff", dash=(4, 2), width=2,
        )

    def _on_mouse_drag(self, event) -> None:
        if self.drag_start is None or self.preview_id is None:
            return
        x0, y0 = self.drag_start
        self.canvas.coords(self.preview_id, x0, y0, event.x, event.y)

    def _on_mouse_up(self, event) -> None:
        if self.drag_start is None or self.selected is None:
            return
        x0, y0 = self.drag_start
        x1, y1 = event.x, event.y
        if abs(x1 - x0) < 4 or abs(y1 - y0) < 4:
            # Treat as a click → ignore.
            self.canvas.delete(self.preview_id)
            self.preview_id = None
            self.drag_start = None
            return
        new_ratio = self._canvas_to_ratio(x0, y0, x1, y1)
        g, i = self.selected
        self.targets[g][i] = new_ratio
        self.canvas.delete(self.preview_id)
        self.preview_id = None
        self.drag_start = None
        self._redraw_all()
        self.status.config(text=f"Updated {g} #{i}\n→ ratios {new_ratio}")

    def _on_right_click(self, event) -> None:
        # Find which rect was clicked.
        for (g, i), rid in self.rect_ids.items():
            x0, y0, x1, y1 = self.canvas.coords(rid)
            if x0 <= event.x <= x1 and y0 <= event.y <= y1:
                self.targets[g][i] = self.defaults[g][i]
                self._redraw_all()
                self.status.config(text=f"Reset {g} #{i}")
                return

    # ── persistence ──────────────────────────────────────────

    def _reset_selected(self) -> None:
        if self.selected is None:
            return
        g, i = self.selected
        self.targets[g][i] = self.defaults[g][i]
        self._redraw_all()
        self.status.config(text=f"Reset {g} #{i}")

    def _save(self) -> None:
        payload = {
            "equipment": [list(r) for r in self.targets["equipment"]],
            "border":    [list(r) for r in self.targets["border"]],
            "bg":        [list(r) for r in self.targets["bg"]],
            "mount":     list(self.targets["mount"][0]),
            "pets":      [list(r) for r in self.targets["pets"]],
            "skills":    [list(r) for r in self.targets["skills"]],
        }
        write_overrides(payload)
        messagebox.showinfo("Saved", "Wrote data/opponent_offsets.json")


# ────────────────────────────────────────────────────────────
#  CLI entry
# ────────────────────────────────────────────────────────────


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[2].strip())
    parser.add_argument("--image", type=Path,
                        help="Opponent screenshot (file picker if omitted)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s")

    image_path: Optional[Path] = args.image
    root = tk.Tk()
    if image_path is None:
        image_path = Path(filedialog.askopenfilename(
            title="Pick opponent screenshot",
            filetypes=[("PNG / JPEG", "*.png *.jpg *.jpeg")],
        ))
        if not image_path or not image_path.exists():
            print("No image selected, aborting.")
            return 1
    if not image_path.exists():
        print(f"Image not found: {image_path}")
        return 1

    CalibratorApp(root, image_path)
    root.mainloop()
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
