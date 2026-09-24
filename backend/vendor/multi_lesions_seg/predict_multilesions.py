#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Single-image inference for the IDRiD HE+EX+SE multiclass VM-UNet model.

Task definition
---------------
0 = BG
1 = HE (Haemorrhages)
2 = EX (Hard Exudates)
3 = SE (Soft Exudates)

The inference pipeline is intentionally kept consistent with training/validation:
1. Read ONE original retinal image.
2. Detect the largest retinal FOV using the same threshold/component logic.
3. Crop the FOV without resizing.
4. ImageNet normalization.
5. Sliding-window inference: 512x512 patches, stride 256.
6. Softmax each patch, average overlapping probabilities, then argmax.
7. Restore the prediction to the ORIGINAL image coordinates.
8. Save:
   - class-index mask
   - color mask
   - overlay on original image
   - HE / EX / SE binary masks

This file is designed both for command-line use and for importing
`predict_one_image()` into a deployment platform.
"""

import json
import time
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage
import torch
import torch.nn.functional as F

from models.vmunet.vmunet import VMUNet


# ============================================================
# Model / task settings: MUST match training
# ============================================================

NUM_CLASSES = 4
CLASS_NAMES = ["BG", "HE", "EX", "SE"]

MODEL_CONFIG = {
    "num_classes": 4,
    "input_channels": 3,
    "depths": [2, 2, 2, 2],
    "depths_decoder": [2, 2, 2, 1],
    "drop_path_rate": 0.2,
    "load_ckpt_path": None,
}

PATCH_SIZE = 512
STRIDE = 256
SW_BATCH_SIZE = 4

# Same FOV settings used by preprocessing
FOV_THRESHOLD = 10
FOV_MARGIN = 5

# Same ImageNet normalization used by dataset_multilesion.py
IMAGENET_MEAN = torch.tensor(
    [0.485, 0.456, 0.406], dtype=torch.float32
).view(3, 1, 1)

IMAGENET_STD = torch.tensor(
    [0.229, 0.224, 0.225], dtype=torch.float32
).view(3, 1, 1)

# Visualization colors (RGB)
# BG is black in the color mask; overlay only paints lesion pixels.
CLASS_COLORS = {
    0: (0, 0, 0),       # BG
    1: (255, 0, 0),     # HE - red
    2: (255, 215, 0),   # EX - yellow
    3: (0, 255, 0),     # SE - green
}


# ============================================================
# Basic preprocessing
# ============================================================

def rgb_to_gray(rgb: np.ndarray) -> np.ndarray:
    """OpenCV-free RGB -> grayscale, matching preprocessing."""
    rgb_f = rgb.astype(np.float32)
    gray = (
        0.299 * rgb_f[..., 0]
        + 0.587 * rgb_f[..., 1]
        + 0.114 * rgb_f[..., 2]
    )
    return gray


def largest_fov_bbox(rgb: np.ndarray):
    """
    Find the largest connected retinal foreground component.
    Returns x0, y0, x1, y1 in ORIGINAL image coordinates.
    """
    gray = rgb_to_gray(rgb)
    fg = gray > FOV_THRESHOLD

    structure = np.ones((3, 3), dtype=np.uint8)
    labeled, num_features = ndimage.label(fg, structure=structure)

    if num_features == 0:
        return 0, 0, rgb.shape[1], rgb.shape[0]

    component_sizes = np.bincount(labeled.ravel())
    component_sizes[0] = 0
    largest_label = int(component_sizes.argmax())

    ys, xs = np.where(labeled == largest_label)
    if xs.size == 0 or ys.size == 0:
        return 0, 0, rgb.shape[1], rgb.shape[0]

    x_min = int(xs.min())
    x_max = int(xs.max()) + 1
    y_min = int(ys.min())
    y_max = int(ys.max()) + 1

    x0 = max(0, x_min - FOV_MARGIN)
    y0 = max(0, y_min - FOV_MARGIN)
    x1 = min(rgb.shape[1], x_max + FOV_MARGIN)
    y1 = min(rgb.shape[0], y_max + FOV_MARGIN)

    return x0, y0, x1, y1


def image_to_tensor(rgb: np.ndarray) -> torch.Tensor:
    """
    RGB uint8 [H,W,3] -> normalized float tensor [1,3,H,W].
    Exactly matches training normalization.
    """
    x = torch.from_numpy(rgb.copy()).permute(2, 0, 1).float() / 255.0
    x = (x - IMAGENET_MEAN) / IMAGENET_STD
    return x.unsqueeze(0)


# ============================================================
# Sliding-window inference
# ============================================================

def _positions(length: int, patch: int, stride: int):
    if length <= patch:
        return [0]

    pos = list(range(0, length - patch + 1, stride))
    last = length - patch
    if pos[-1] != last:
        pos.append(last)
    return pos


@torch.no_grad()
def sliding_window_probs(
    model,
    image,
    num_classes=NUM_CLASSES,
    patch_size=PATCH_SIZE,
    stride=STRIDE,
    sw_batch_size=SW_BATCH_SIZE,
):
    """
    image: [1,3,H,W], already normalized.
    Returns overlap-averaged probabilities [1,C,H,W].

    This follows engine_multilesion.py:
    patch -> model -> softmax -> overlap probability accumulation -> average.
    """
    assert image.ndim == 4 and image.size(0) == 1

    _, _, H, W = image.shape

    pad_h = max(0, patch_size - H)
    pad_w = max(0, patch_size - W)

    if pad_h or pad_w:
        # Match validation/test code: pad normalized tensor with 0.
        image_pad = F.pad(
            image,
            (0, pad_w, 0, pad_h),
            mode="constant",
            value=0.0,
        )
    else:
        image_pad = image

    Hp, Wp = image_pad.shape[-2:]

    ys = _positions(Hp, patch_size, stride)
    xs = _positions(Wp, patch_size, stride)

    prob_sum = torch.zeros(
        (1, num_classes, Hp, Wp),
        device=image.device,
        dtype=torch.float32,
    )
    count = torch.zeros(
        (1, 1, Hp, Wp),
        device=image.device,
        dtype=torch.float32,
    )

    coords = []
    patches = []

    def flush():
        nonlocal coords, patches, prob_sum, count

        if not patches:
            return

        batch = torch.cat(patches, dim=0)
        logits = model(batch)

        if isinstance(logits, (tuple, list)):
            logits = logits[0]

        probs = torch.softmax(logits, dim=1)

        for i, (y, x) in enumerate(coords):
            prob_sum[:, :, y:y + patch_size, x:x + patch_size] += probs[i:i + 1]
            count[:, :, y:y + patch_size, x:x + patch_size] += 1.0

        coords = []
        patches = []

    for y in ys:
        for x in xs:
            patches.append(image_pad[:, :, y:y + patch_size, x:x + patch_size])
            coords.append((y, x))

            if len(patches) >= sw_batch_size:
                flush()

    flush()

    probs = prob_sum / count.clamp_min(1.0)
    return probs[:, :, :H, :W]


# ============================================================
# Model loading
# ============================================================

def build_model():
    return VMUNet(
        num_classes=MODEL_CONFIG["num_classes"],
        input_channels=MODEL_CONFIG["input_channels"],
        depths=MODEL_CONFIG["depths"],
        depths_decoder=MODEL_CONFIG["depths_decoder"],
        drop_path_rate=MODEL_CONFIG["drop_path_rate"],
        load_ckpt_path=MODEL_CONFIG["load_ckpt_path"],
    )


def _torch_load_compat(path, map_location):
    """
    Compatible with both older and newer PyTorch versions.
    For the saved best_mdice.pth, weights_only=True is sufficient.
    """
    try:
        return torch.load(path, map_location=map_location, weights_only=True)
    except TypeError:
        return torch.load(path, map_location=map_location)


def load_model(weight_path, device):
    weight_path = Path(weight_path)
    if not weight_path.exists():
        raise FileNotFoundError(f"Weight file not found: {weight_path}")

    model = build_model()

    ckpt = _torch_load_compat(str(weight_path), map_location="cpu")

    # Support both:
    # 1) torch.save(model.state_dict(), ...)
    # 2) {"model_state_dict": ...}
    # 3) {"state_dict": ...}
    if isinstance(ckpt, dict) and "model_state_dict" in ckpt:
        state_dict = ckpt["model_state_dict"]
    elif isinstance(ckpt, dict) and "state_dict" in ckpt:
        state_dict = ckpt["state_dict"]
    else:
        state_dict = ckpt

    if not isinstance(state_dict, dict):
        raise RuntimeError(
            "Unsupported checkpoint format. Expected a state_dict or a dict "
            "containing 'model_state_dict'/'state_dict'."
        )

    # Allow checkpoints saved from DataParallel / DDP.
    if any(k.startswith("module.") for k in state_dict.keys()):
        state_dict = {
            k[7:] if k.startswith("module.") else k: v
            for k, v in state_dict.items()
        }

    model.load_state_dict(state_dict, strict=False)
    model.to(device)
    model.eval()

    return model


# ============================================================
# Visualization / output
# ============================================================

def class_index_to_color(mask: np.ndarray) -> np.ndarray:
    """Class-index mask [H,W] -> RGB color mask [H,W,3]."""
    color = np.zeros((*mask.shape, 3), dtype=np.uint8)

    for class_id, rgb_color in CLASS_COLORS.items():
        color[mask == class_id] = rgb_color

    return color


def make_overlay(
    original_rgb: np.ndarray,
    mask: np.ndarray,
    alpha: float = 0.45,
) -> np.ndarray:
    """
    Paint lesion classes on the original image.
    Background pixels remain exactly unchanged.
    """
    alpha = float(np.clip(alpha, 0.0, 1.0))

    overlay = original_rgb.astype(np.float32).copy()
    color_mask = class_index_to_color(mask).astype(np.float32)

    lesion = mask > 0

    overlay[lesion] = (
        (1.0 - alpha) * overlay[lesion]
        + alpha * color_mask[lesion]
    )

    return np.clip(overlay, 0, 255).astype(np.uint8)


def save_outputs(
    original_rgb,
    full_mask,
    probs_crop,
    bbox,
    image_path,
    output_dir,
    alpha=0.45,
    save_probabilities=False,
):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    image_path = Path(image_path)
    stem = image_path.stem

    # 1) Original-size class-index mask: 0/1/2/3
    index_path = output_dir / f"{stem}_mask_index.png"
    Image.fromarray(full_mask.astype(np.uint8), mode="L").save(index_path)

    # 2) Original-size color mask
    color_mask = class_index_to_color(full_mask)
    color_path = output_dir / f"{stem}_mask_color.png"
    Image.fromarray(color_mask, mode="RGB").save(color_path)

    # 3) Overlay on ORIGINAL image
    overlay = make_overlay(original_rgb, full_mask, alpha=alpha)
    overlay_path = output_dir / f"{stem}_overlay.png"
    Image.fromarray(overlay, mode="RGB").save(overlay_path)

    # 4) Separate binary lesion masks, useful for platform integration
    lesion_paths = {}
    for class_id, class_name in [(1, "HE"), (2, "EX"), (3, "SE")]:
        binary = np.where(full_mask == class_id, 255, 0).astype(np.uint8)
        p = output_dir / f"{stem}_{class_name}.png"
        Image.fromarray(binary, mode="L").save(p)
        lesion_paths[class_name] = str(p)

    # 5) Optional probability maps from cropped FOV
    prob_path = None
    if save_probabilities:
        prob_path = output_dir / f"{stem}_probabilities_fov.npz"
        np.savez_compressed(
            prob_path,
            BG=probs_crop[0],
            HE=probs_crop[1],
            EX=probs_crop[2],
            SE=probs_crop[3],
        )

    pixel_counts = {
        CLASS_NAMES[c]: int((full_mask == c).sum())
        for c in range(NUM_CLASSES)
    }

    summary = {
        "input_image": str(image_path),
        "original_width": int(original_rgb.shape[1]),
        "original_height": int(original_rgb.shape[0]),
        "fov_bbox_xyxy": [int(v) for v in bbox],
        "patch_size": PATCH_SIZE,
        "stride": STRIDE,
        "classes": {
            "0": "BG",
            "1": "HE",
            "2": "EX",
            "3": "SE",
        },
        "pixel_counts": pixel_counts,
        "outputs": {
            "mask_index": str(index_path),
            "mask_color": str(color_path),
            "overlay": str(overlay_path),
            **lesion_paths,
        },
    }

    if prob_path is not None:
        summary["outputs"]["probabilities_fov"] = str(prob_path)

    json_path = output_dir / f"{stem}_result.json"
    json_path.write_text(
        json.dumps(summary, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    summary["outputs"]["json"] = str(json_path)
    return summary


# ============================================================
# Public deployment API
# ============================================================

@torch.no_grad()
def predict_one_image(
    image_path,
    weight_path,
    output_dir="./predict_results",
    device=None,
    alpha=0.45,
    save_probabilities=False,
    model=None,
):
    """
    Predict ONE original retinal image.

    Parameters
    ----------
    image_path : str / Path
        Original input image path.
    weight_path : str / Path
        Trained checkpoint, e.g. best_mdice.pth.
    output_dir : str / Path
        Directory for prediction outputs.
    device : str / torch.device / None
        None -> cuda if available, otherwise cpu.
    alpha : float
        Overlay transparency.
    save_probabilities : bool
        Save cropped-FOV probability maps as NPZ.
    model : torch.nn.Module / None
        Optional already-loaded model.
        For a web platform, load the model ONCE and reuse it for every image.

    Returns
    -------
    dict
        Output paths, bbox, pixel counts, inference time, etc.
    """
    image_path = Path(image_path)
    if not image_path.exists():
        raise FileNotFoundError(f"Input image not found: {image_path}")

    if device is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    else:
        device = torch.device(device)

    if model is None:
        model = load_model(weight_path, device)
    else:
        model = model.to(device)
        model.eval()

    # Read original image
    original_rgb = np.array(Image.open(image_path).convert("RGB"))
    orig_h, orig_w = original_rgb.shape[:2]

    # Same FOV crop as preprocessing
    x0, y0, x1, y1 = largest_fov_bbox(original_rgb)
    rgb_crop = original_rgb[y0:y1, x0:x1]

    # Same normalization as training
    image_tensor = image_to_tensor(rgb_crop).to(device, non_blocking=True).float()

    if device.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.time()

    probs = sliding_window_probs(
        model=model,
        image=image_tensor,
        num_classes=NUM_CLASSES,
        patch_size=PATCH_SIZE,
        stride=STRIDE,
        sw_batch_size=SW_BATCH_SIZE,
    )

    pred_crop = torch.argmax(probs, dim=1)[0].cpu().numpy().astype(np.uint8)
    probs_crop = probs[0].cpu().numpy().astype(np.float32)

    if device.type == "cuda":
        torch.cuda.synchronize()
    inference_seconds = time.time() - t0

    # Restore prediction to ORIGINAL image coordinates.
    # Outside retinal FOV = BG.
    full_mask = np.zeros((orig_h, orig_w), dtype=np.uint8)
    full_mask[y0:y1, x0:x1] = pred_crop

    result = save_outputs(
        original_rgb=original_rgb,
        full_mask=full_mask,
        probs_crop=probs_crop,
        bbox=(x0, y0, x1, y1),
        image_path=image_path,
        output_dir=output_dir,
        alpha=alpha,
        save_probabilities=save_probabilities,
    )

    result["device"] = str(device)
    result["inference_seconds"] = float(inference_seconds)

    print("\nPrediction finished.")
    print(f"Input:   {image_path}")
    print(f"Device:  {device}")
    print(f"FOV:     x0={x0}, y0={y0}, x1={x1}, y1={y1}")
    print(f"Time:    {inference_seconds:.3f} s")
    print(f"HE px:   {result['pixel_counts']['HE']}")
    print(f"EX px:   {result['pixel_counts']['EX']}")
    print(f"SE px:   {result['pixel_counts']['SE']}")
    print("Outputs:")
    for k, v in result["outputs"].items():
        print(f"  {k}: {v}")

    return result


# ============================================================
# Direct-input settings
# ============================================================

# 直接在这里修改即可，不需要命令行参数。
# 输入：一张原始眼底图像
INPUT_IMAGE = r"/home/zh8211220706/Huiyan/multi_seg_lesions/IDRID/1. Original Images/a. Training Set/IDRiD_50.jpg"

# 推荐使用训练得到的 best_mdice.pth
WEIGHT_PATH = r"./weights/best_mdice.pth"

# 所有结果都会保存到这里
OUTPUT_DIR = r"./predict_results"

# None: 自动选择 GPU / CPU
# 也可以写 "cuda:0" 或 "cpu"
DEVICE = None

# 原图叠加透明度，范围 0~1
OVERLAY_ALPHA = 0.45

# 是否额外保存 BG/HE/EX/SE 概率图 npz
SAVE_PROBABILITIES = False


def main():
    predict_one_image(
        image_path=INPUT_IMAGE,
        weight_path=WEIGHT_PATH,
        output_dir=OUTPUT_DIR,
        device=DEVICE,
        alpha=OVERLAY_ALPHA,
        save_probabilities=SAVE_PROBABILITIES,
    )


if __name__ == "__main__":
    main()
