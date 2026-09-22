"""上传眼别自动判断：合成图覆盖左、右、双、未知，不依赖真实数据集。"""

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from app.common.eye_infer import (
    filename_eye_hint,
    infer_eye_laterality,
    laterality_from_paths,
    resolve_uploaded_eye,
)

ROOT = Path(__file__).resolve().parents[1]
IDRID_76 = ROOT / "app" / "static" / "training" / "idrid" / "originals" / "IDRiD_76.jpg"
IDRID_02 = ROOT / "app" / "static" / "training" / "idrid" / "originals" / "IDRiD_02.jpg"


def _fundus(path: Path, centers, size=(360, 180), radius=55):
    h, w = size[1], size[0]
    img = np.zeros((h, w, 3), dtype=np.uint8)
    yy, xx = np.ogrid[:h, :w]
    for cx, cy in centers:
        disc = (xx - cx) ** 2 + (yy - cy) ** 2 <= radius ** 2
        img[disc] = (90, 50, 40)
        core = (xx - cx) ** 2 + (yy - cy) ** 2 <= 12 ** 2
        img[core] = (255, 250, 240)
    Image.fromarray(img).save(path)
    return path


def test_bright_blob_on_the_right_is_od(tmp_path):
    path = _fundus(tmp_path / "right.png", [(280, 90)])
    assert infer_eye_laterality(path) == "OD"


def test_bright_blob_on_the_left_is_os(tmp_path):
    path = _fundus(tmp_path / "left.png", [(80, 90)])
    assert infer_eye_laterality(path) == "OS"


def test_two_separate_fundus_is_ou(tmp_path):
    path = _fundus(tmp_path / "both.png", [(80, 90), (280, 90)])
    assert infer_eye_laterality(path) == "OU"


def test_flat_image_is_unknown(tmp_path):
    path = tmp_path / "flat.png"
    Image.fromarray(np.full((180, 180, 3), 40, dtype=np.uint8)).save(path)
    assert infer_eye_laterality(path) == "UK"


def test_centered_disc_is_unknown(tmp_path):
    path = _fundus(tmp_path / "mid.png", [(180, 90)])
    assert infer_eye_laterality(path) == "UK"


def test_filename_does_not_treat_disc_mask_suffix_as_right_eye():
    assert filename_eye_hint("IDRiD_76_OD.png") is None
    assert filename_eye_hint("patient_右眼.jpg") == "OD"
    assert filename_eye_hint("left eye.png") == "OS"
    assert filename_eye_hint("双眼.jpg") == "OU"


def test_explicit_choice_is_kept_even_when_image_says_otherwise(tmp_path):
    path = _fundus(tmp_path / "right.png", [(280, 90)])
    assert resolve_uploaded_eye("OS", file_name="右眼.jpg", image_path=path) == "OS"


def test_unknown_eye_uses_image_before_conflicting_filename(tmp_path):
    path = _fundus(tmp_path / "right.png", [(280, 90)])
    assert resolve_uploaded_eye("UK", file_name="左眼.jpg", image_path=path) == "OD"


def test_filename_hint_used_only_when_image_is_ambiguous(tmp_path):
    path = tmp_path / "flat.png"
    Image.fromarray(np.full((180, 180, 3), 40, dtype=np.uint8)).save(path)
    assert resolve_uploaded_eye("", file_name="右眼.png", image_path=path) == "OD"


def test_mask_inherits_the_only_original_eye_and_skips_disc_detection(tmp_path):
    path = _fundus(tmp_path / "right.png", [(280, 90)])
    assert resolve_uploaded_eye(
        "UK", file_name="lesion.png", image_path=path, role="MA", inherited="OS",
    ) == "OS"


def test_laterality_from_paths_does_not_call_uk_binocular():
    assert laterality_from_paths({"OD": ["/a.jpg"]}) == "OD"
    assert laterality_from_paths({"OS": ["/a.jpg"]}) == "OS"
    assert laterality_from_paths({"OU": ["/a.jpg"]}) == "OU"
    assert laterality_from_paths({"UK": ["/a.jpg"]}) == "UK"
    assert laterality_from_paths({"OD": ["/a.jpg"], "OS": ["/b.jpg"]}) == "OU"
    assert laterality_from_paths({}) == "UK"


@pytest.mark.skipif(not IDRID_76.is_file(), reason="本地没有 IDRiD_76 原图")
def test_idrid_76_infers_right_eye():
    assert infer_eye_laterality(IDRID_76) == "OD"


@pytest.mark.skipif(not IDRID_02.is_file(), reason="本地没有 IDRiD_02 原图")
def test_idrid_02_infers_left_eye():
    assert infer_eye_laterality(IDRID_02) == "OS"
