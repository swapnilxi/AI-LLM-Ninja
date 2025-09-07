import argparse, json, random, shutil
from pathlib import Path
import numpy as np
import cv2
from scipy.io import loadmat

INDOOR_CLASSES = [
    "bed","chair","table","sofa","lamp","cabinet","window","door",
    "bookshelf","picture","pillow","sink","toilet","mirror","curtain",
    "refrigerator","tv","nightstand","counter","desk"
]
CLASS_TO_ID = {c:i for i,c in enumerate(INDOOR_CLASSES)}

ALIASES = {
    "television":"tv", "tvmonitor":"tv", "bookcase":"bookshelf",
    "night table":"nightstand", "pictureframe":"picture"
}

def clamp_bbox_xyxy(xmin, ymin, xmax, ymax, W, H):
    xmin = max(0, min(float(xmin), W-1))
    ymin = max(0, min(float(ymin), H-1))
    xmax = max(0, min(float(xmax), W-1))
    ymax = max(0, min(float(ymax), H-1))
    w = xmax - xmin
    h = ymax - ymin
    if w <= 1 or h <= 1: 
        return None
    cx = xmin + w/2.0
    cy = ymin + h/2.0
    return cx/W, cy/H, w/W, h/H

def xywh_to_xyxy(x, y, w, h):
    return x, y, x + w, y + h

def parse_objects(mat):
    """Try common layouts seen in annotation2Dfinal.mat:
       - gt = mat['groundtruth'][0][0]['objects'][0]
       - gt = mat['annotation2D'][0][0]['object'][0]
       - gt = mat['anno2Dfinal']['object'] ...
    """
    keys = mat.keys()
    candidates = []
    for k in ("groundtruth", "annotation2D", "anno2Dfinal", "objects", "object"):
        if k in keys:
            candidates.append(k)

    # Heuristic dig:
    root = None
    for k in ("groundtruth", "annotation2D", "anno2Dfinal"):
        if k in mat:
            root = mat[k]
            break
    if root is None:
        return []

    # Pull objects array
    objs = None
    try:
        # shape like (1,1) with dtype having 'objects' or 'object'
        node = root[0][0] if root.ndim==2 else root
        for ok in ("objects","object"):
            if ok in node.dtype.names:
                objs = node[ok][0]
                break
    except Exception:
        pass

    if objs is None:
        # sometimes it's already an array of structs
        if isinstance(root, np.ndarray) and root.dtype.names:
            objs = root
        else:
            return []

    return objs

def get_name(o):
    for k in ("classname","name","label","class"):
        if k in o.dtype.names:
            v = o[k]
            try:
                return str(v[0]) if isinstance(v, np.ndarray) else str(v)
            except Exception:
                pass
    return None

def get_bbox(o):
    # Return xyxy in pixels if possible
    # 1) packed 'bbox' -> could be [x, y, w, h] or [xmin, ymin, xmax, ymax]
    if "bbox" in o.dtype.names:
        b = np.squeeze(o["bbox"])
        if b.size >= 4:
            x, y, w, h = float(b[0]), float(b[1]), float(b[2]), float(b[3])
            # heuristic: if w,h already bigger than x,y and (x+w, y+h) < reasonable bounds, treat as xywh
            # else assume it was xmin,ymin,xmax,ymax
            if w > 0 and h > 0 and (x <= x+w) and (y <= y+h):
                return xywh_to_xyxy(x, y, w, h)
            else:
                return x, y, w, h
    # 2) explicit fields
    fieldset = set(o.dtype.names)
    if {"xmin","ymin","xmax","ymax"}.issubset(fieldset):
        return float(o["xmin"]), float(o["ymin"]), float(o["xmax"]), float(o["ymax"])
    if {"x","y","w","h"}.issubset(fieldset):
        return xywh_to_xyxy(float(o["x"]), float(o["y"]), float(o["w"]), float(o["h"]))
    # 3) sometimes 'bndbox' or 'bb2D' or '2Dbb'
    for k in ("bndbox","bb2D","2Dbb"):
        if k in fieldset:
            b = np.squeeze(o[k])
            if b.size >= 4:
                return xywh_to_xyxy(float(b[0]), float(b[1]), float(b[2]), float(b[3]))
    return None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--meta", required=True, help="text file with 'image_path mat_path' per line")
    ap.add_argument("--out-root", default="room_dataset/yolo_sunrgbd")
    ap.add_argument("--split-ratio", type=float, default=0.9)
    args = ap.parse_args()

    pairs = [ln.strip().split() for ln in Path(args.meta).read_text().strip().splitlines()]
    random.seed(42)
    random.shuffle(pairs)
    sp = int(len(pairs)*args.split_ratio)
    splits = {"train": pairs[:sp], "val": pairs[sp:]}

    for split, items in splits.items():
        (Path(args.out_root)/split/"images").mkdir(parents=True, exist_ok=True)
        (Path(args.out_root)/split/"labels").mkdir(parents=True, exist_ok=True)
        for img_p, mat_p in items:
            img_p, mat_p = Path(img_p), Path(mat_p)
            img = cv2.imread(str(img_p))
            if img is None:
                continue
            H, W = img.shape[:2]
            try:
                ann = loadmat(str(mat_p), squeeze_me=True, struct_as_record=False)
            except Exception:
                continue

            objs = parse_objects(ann)
            if objs is None or len(objs) == 0:
                continue

            lines = []
            for o in objs:
                name = get_name(o)
                if not name: 
                    continue
                name = name.lower().strip()
                if name in ALIASES: name = ALIASES[name]
                if name not in CLASS_TO_ID:
                    continue
                bb = get_bbox(o)
                if not bb: 
                    continue
                cxcywh = clamp_bbox_xyxy(*bb, W=W, H=H)
                if not cxcywh:
                    continue
                cx, cy, w, h = cxcywh
                lines.append(f"{CLASS_TO_ID[name]} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}")

            if not lines:
                continue

            out_img = Path(args.out_root)/split/"images"/img_p.name
            out_lbl = Path(args.out_root)/split/"labels"/(img_p.stem + ".txt")
            shutil.copy2(img_p, out_img)
            with open(out_lbl, "w") as f:
                f.write("\n".join(lines))

    (Path(args.out_root)/"classes.json").write_text(json.dumps(INDOOR_CLASSES, indent=2))
    print("✓ Done:", Path(args.out_root).resolve())

if __name__ == "__main__":
    main()
