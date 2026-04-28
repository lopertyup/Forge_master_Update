# tools/debug_offsets.py
"""
Lance ce script avec une capture pour visualiser où les offsets
tombent sur l'image. Ça dessine chaque rectangle et le sauvegarde.

    python -m tools.debug_offsets path/to/screenshot.png --mode opponent
    python -m tools.debug_offsets path/to/screenshot.png --mode player
"""
from __future__ import annotations
import argparse
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


def draw_offsets(img_path: str, mode: str = "opponent") -> None:
    img = Image.open(img_path).convert("RGB")
    W, H = img.size
    draw = ImageDraw.Draw(img)

    if mode == "opponent":
        from backend.scanner.offsets.opponent import offsets_for_capture
    else:
        from backend.scanner.offsets.player import offsets_for_capture

    offsets = offsets_for_capture(W, H)
    slot_order = list(offsets.get("slot_order", []))

    # Équipements — vert
    for i, (x0, y0, x1, y1) in enumerate(offsets["equipment"]):
        draw.rectangle([x0, y0, x1, y1], outline="lime", width=2)
        label = slot_order[i] if i < len(slot_order) else str(i)
        draw.text((x0 + 2, y0 + 2), label, fill="lime")

    # Bordures rareté — bleu
    for x0, y0, x1, y1 in offsets["border"]:
        draw.rectangle([x0, y0, x1, y1], outline="cyan", width=1)

    # Background âge — jaune
    for x0, y0, x1, y1 in offsets["bg"]:
        draw.rectangle([x0, y0, x1, y1], outline="yellow", width=1)

    # Bande OCR niveau (sous chaque icône équipement)
    for x0, y0, x1, y1 in offsets["equipment"]:
        h = y1 - y0
        strip_y0 = min(H, y1 - int(h * 0.20))
        strip_y1 = min(H, y1 + int(h * 0.50))
        draw.rectangle([x0, strip_y0, x1, strip_y1], outline="orange", width=1)

    # Pets / mount / skills (mode opponent seulement)
    for x0, y0, x1, y1 in offsets.get("pets", []):
        draw.rectangle([x0, y0, x1, y1], outline="magenta", width=2)
    for x0, y0, x1, y1 in offsets.get("mount", []):
        draw.rectangle([x0, y0, x1, y1], outline="red", width=2)
    for x0, y0, x1, y1 in offsets.get("skills", []):
        draw.rectangle([x0, y0, x1, y1], outline="white", width=2)

    out = Path(img_path).with_stem(Path(img_path).stem + f"_debug_{mode}")
    img.save(out)
    print(f"Sauvegardé : {out}")
    print(f"Taille image : {W}×{H}")
    print(f"Slots équipement :")
    for i, rect in enumerate(offsets["equipment"]):
        print(f"  [{slot_order[i] if i < len(slot_order) else i}] {rect}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("image")
    parser.add_argument("--mode", choices=["opponent", "player"], default="opponent")
    args = parser.parse_args()
    draw_offsets(args.image, args.mode)