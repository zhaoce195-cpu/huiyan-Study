"""
DRGCNN API · Python 集成参考实现
================================

适用场景：
- 后端集成 DRGCNN 双眼 DR 预测 API（http://113.219.243.122:9050）
- 支持 URL / 本地文件路径 / Base64 三种输入；自动归一化为服务端可识别的字符串
- 提供结果解析、批量数据集分析示例

依赖：
    pip install requests

直接运行（演示）：
    python drgcnn_client.py
"""

from __future__ import annotations

import base64
import logging
import mimetypes
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# ============================================================
# 0. 常量 / 配置
# ============================================================

DEFAULT_BASE_URL = "http://113.219.243.122:9050"
DEFAULT_TIMEOUT = 30  # 秒；服务端单次推理 3-10s + URL 拉取最多 20s
PREDICT_PATH = "/predict_twoeyes"
GRADES_PATH = "/dataset/grades"
IMAGES_PATH = "/dataset/images/{grade}"
IMAGE_BASE64_PATH = "/dataset/image_base64/{grade}/{filename}"

# DR 等级中文映射，对接前端 UI 直接展示
GRADE_TEXT: Dict[int, str] = {
    0: "无 DR",
    1: "轻度 NPDR",
    2: "中度 NPDR",
    3: "重度 NPDR",
    4: "增殖性 PDR",
}

# 仅保留这些扩展名的本地文件，避免误把非图片当成图片读
ALLOWED_LOCAL_EXT = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# 服务端 URL 加载超时是 20s，本地 base64 编码后体积较大，单次请求建议 ≤ 8MB
MAX_IMAGE_BYTES = 8 * 1024 * 1024

logger = logging.getLogger("drgcnn")


# ============================================================
# 1. 输入归一化：URL / 本地路径 / Base64 → 服务端可识别字符串
# ============================================================

def _is_http_url(s: str) -> bool:
    if not s:
        return False
    parsed = urlparse(s)
    return parsed.scheme in ("http", "https") and bool(parsed.netloc)


def _is_data_url(s: str) -> bool:
    return isinstance(s, str) and s.startswith("data:") and ";base64," in s


def _local_to_data_url(path: Union[str, Path]) -> str:
    """读取本地图片 → 转成 data:image/...;base64,... 字符串"""
    p = Path(path)
    if not p.exists() or not p.is_file():
        raise FileNotFoundError(f"图像文件不存在: {p}")
    if p.suffix.lower() not in ALLOWED_LOCAL_EXT:
        raise ValueError(f"不支持的图像扩展名: {p.suffix}")
    raw = p.read_bytes()
    if len(raw) == 0:
        raise ValueError(f"图像文件为空: {p}")
    if len(raw) > MAX_IMAGE_BYTES:
        raise ValueError(
            f"图像过大（{len(raw)/1024/1024:.1f}MB），"
            f"建议先压缩到 {MAX_IMAGE_BYTES/1024/1024:.0f}MB 以内"
        )
    mime = mimetypes.guess_type(str(p))[0] or "image/jpeg"
    b64 = base64.b64encode(raw).decode("ascii")
    return f"data:{mime};base64,{b64}"


def normalize_image_input(image: Union[str, Path, bytes]) -> str:
    """
    将任意支持的输入类型归一化为「可直接放进 leftUrl/rightUrl 的字符串」：
    - http(s):// 开头   → 直接用
    - data:image/...;base64,...  → 直接用
    - 本地路径（Path 或 str） → 读为 data URL
    - bytes → 当作图片字节，直接编码成 data URL（默认 jpeg）
    """
    if isinstance(image, bytes):
        if len(image) == 0:
            raise ValueError("图像字节流为空")
        b64 = base64.b64encode(image).decode("ascii")
        return f"data:image/jpeg;base64,{b64}"

    s = str(image).strip()
    if _is_http_url(s) or _is_data_url(s):
        return s
    return _local_to_data_url(s)


# ============================================================
# 2. 客户端：连接复用 + 重试 + 超时
# ============================================================

class DRGCNNClient:
    """对接 DRGCNN API 的轻量客户端。

    约定：
    - 每次调用都返回原始 JSON dict；解析交给 :func:`parse_predict_result`
    - HTTP 异常/解析失败统一抛 :class:`DRGCNNError`
    """

    def __init__(
        self,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = 2,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=0.6,
            status_forcelist=[502, 503, 504],
            allowed_methods=frozenset(["GET", "POST"]),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_maxsize=8)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

    # ---------------- 核心：双眼预测 ----------------

    def predict_twoeyes(
        self,
        left: Union[str, Path, bytes],
        right: Union[str, Path, bytes],
    ) -> Dict[str, Any]:
        """提交左右眼图像，返回服务端原始 JSON。"""
        payload = {
            "leftUrl": normalize_image_input(left),
            "rightUrl": normalize_image_input(right),
        }
        url = self.base_url + PREDICT_PATH
        try:
            resp = self.session.post(url, json=payload, timeout=self.timeout)
        except requests.RequestException as e:
            raise DRGCNNError(f"请求 DRGCNN 失败: {e}") from e

        if resp.status_code != 200:
            # 尽量带上服务端的 error 文案
            err_msg = self._extract_error(resp)
            raise DRGCNNError(
                f"DRGCNN 返回非 200 状态：{resp.status_code} {err_msg}",
                status_code=resp.status_code,
            )
        try:
            return resp.json()
        except ValueError as e:
            raise DRGCNNError(f"DRGCNN 响应不是合法 JSON: {e}") from e

    # ---------------- 数据集相关 ----------------

    def dataset_grades(self) -> Dict[str, Any]:
        url = self.base_url + GRADES_PATH
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()

    def dataset_patients(self, grade: int, page: int = 1, limit: int = 20) -> Dict[str, Any]:
        url = self.base_url + IMAGES_PATH.format(grade=grade)
        resp = self.session.get(
            url, params={"page": page, "limit": limit}, timeout=self.timeout,
        )
        resp.raise_for_status()
        return resp.json()

    def dataset_image_base64(self, grade: int, filename: str) -> str:
        url = self.base_url + IMAGE_BASE64_PATH.format(grade=grade, filename=filename)
        resp = self.session.get(url, timeout=self.timeout)
        resp.raise_for_status()
        return resp.json()["base64"]

    # ---------------- 内部 ----------------

    @staticmethod
    def _extract_error(resp: requests.Response) -> str:
        try:
            data = resp.json()
            return str(data.get("error") or data)
        except Exception:
            return resp.text[:300]


class DRGCNNError(RuntimeError):
    def __init__(self, msg: str, status_code: Optional[int] = None) -> None:
        super().__init__(msg)
        self.status_code = status_code


# ============================================================
# 3. 结果解析
# ============================================================

@dataclass
class EyeResult:
    eye: str                # "left" / "right"
    grade: int              # 0~4
    grade_text: str         # "中度 NPDR" 等
    probability: float      # 服务端 *_probability（回归值）
    image_name: str         # 服务端 *_image_name
    heatmap_base64: str     # 完整 data URL，可直接放到 <img src="...">

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class PredictResult:
    left: EyeResult
    right: EyeResult
    # 取双眼最大等级，作为整体风险代表（>=2 通常需就医，>=3 建议尽快转诊）
    max_grade: int
    max_grade_text: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "left": self.left.to_dict(),
            "right": self.right.to_dict(),
            "maxGrade": self.max_grade,
            "maxGradeText": self.max_grade_text,
        }


def parse_predict_result(raw: Dict[str, Any]) -> PredictResult:
    """把 /predict_twoeyes 的原始 JSON 解析成结构化对象。

    关键字段：
    - left_eye_prediction / right_eye_prediction   -> int 0~4
    - left_eye_probability / right_eye_probability -> float
    - left_eye_image_name / right_eye_image_name   -> 文件名
    - left_eye_heatmap_base64 / right_eye_heatmap_base64 -> data:image/jpeg;base64,...
    """
    if not isinstance(raw, dict):
        raise DRGCNNError(f"无效响应：{raw!r}")
    if "error" in raw:
        raise DRGCNNError(f"服务端报错：{raw['error']}")

    def _eye(prefix: str, side: str) -> EyeResult:
        grade = int(raw.get(f"{prefix}_prediction", -1))
        return EyeResult(
            eye=side,
            grade=grade,
            grade_text=GRADE_TEXT.get(grade, f"未知({grade})"),
            probability=float(raw.get(f"{prefix}_probability", 0.0)),
            image_name=str(raw.get(f"{prefix}_image_name", "")),
            heatmap_base64=str(raw.get(f"{prefix}_heatmap_base64", "")),
        )

    left = _eye("left_eye", "left")
    right = _eye("right_eye", "right")
    max_grade = max(left.grade, right.grade)
    return PredictResult(
        left=left,
        right=right,
        max_grade=max_grade,
        max_grade_text=GRADE_TEXT.get(max_grade, f"未知({max_grade})"),
    )


# ============================================================
# 4. 批量分析数据集（用于离线评估 / 灰盒验证）
# ============================================================

def batch_evaluate_grade(
    client: DRGCNNClient,
    grade: int,
    *,
    page_size: int = 20,
    max_patients: Optional[int] = None,
    workers: int = 4,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """对数据集中某个等级的患者批量调用 predict_twoeyes，返回明细 + 汇总指标。

    汇总：
    - left_correct / right_correct：与 grade 相符的眼数
    - confusion：{真实grade -> {预测grade -> 计数}}
    - elapsed_sec：总耗时
    """
    # 1) 拉取该等级全部患者列表（分页）
    patients: List[Dict[str, Any]] = []
    page = 1
    while True:
        page_data = client.dataset_patients(grade, page=page, limit=page_size)
        patients.extend(page_data.get("patients", []))
        total = int(page_data.get("total", 0))
        if max_patients and len(patients) >= max_patients:
            patients = patients[:max_patients]
            break
        if len(patients) >= total:
            break
        page += 1

    # 2) 并行调用预测（单服务器并发不宜过大；建议 4 ~ 8）
    def _job(patient: Dict[str, Any]) -> Dict[str, Any]:
        try:
            left_b64 = client.dataset_image_base64(grade, patient["left"])
            right_b64 = client.dataset_image_base64(grade, patient["right"])
            raw = client.predict_twoeyes(left_b64, right_b64)
            res = parse_predict_result(raw)
            return {
                "patientId": patient["id"],
                "trueGrade": grade,
                "leftPred": res.left.grade,
                "rightPred": res.right.grade,
                "leftProb": res.left.probability,
                "rightProb": res.right.probability,
                "ok": True,
            }
        except Exception as e:
            return {
                "patientId": patient.get("id", ""),
                "trueGrade": grade,
                "ok": False,
                "error": str(e),
            }

    started = time.time()
    results: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_job, p) for p in patients]
        for fut in as_completed(futures):
            results.append(fut.result())
    elapsed = time.time() - started

    # 3) 汇总
    left_correct = sum(1 for r in results if r.get("ok") and r["leftPred"] == grade)
    right_correct = sum(1 for r in results if r.get("ok") and r["rightPred"] == grade)
    summary = {
        "grade": grade,
        "total_patients": len(results),
        "ok": sum(1 for r in results if r.get("ok")),
        "fail": sum(1 for r in results if not r.get("ok")),
        "left_correct": left_correct,
        "right_correct": right_correct,
        "left_acc": left_correct / max(1, len(results)),
        "right_acc": right_correct / max(1, len(results)),
        "elapsed_sec": round(elapsed, 2),
    }
    return results, summary


# ============================================================
# 5. CLI 演示入口
# ============================================================

def _demo_url() -> None:
    client = DRGCNNClient()
    raw = client.predict_twoeyes(
        # 真实使用时换成你的眼底图 URL / 本地路径
        left="https://example.com/left_eye.jpeg",
        right="https://example.com/right_eye.jpeg",
    )
    res = parse_predict_result(raw)
    print(f"双眼最大等级：{res.max_grade} ({res.max_grade_text})")
    print(f"左眼：{res.left.grade_text} (p={res.left.probability:.3f})")
    print(f"右眼：{res.right.grade_text} (p={res.right.probability:.3f})")


def _demo_local() -> None:
    client = DRGCNNClient()
    raw = client.predict_twoeyes(
        left=Path("samples/left.jpg"),
        right=Path("samples/right.jpg"),
    )
    res = parse_predict_result(raw)
    print(res.to_dict())


def _demo_dataset_grades() -> None:
    client = DRGCNNClient()
    info = client.dataset_grades()
    for g in info["grades"]:
        print(f"等级 {g['grade']}: {g['count']} 张")


def _demo_batch() -> None:
    client = DRGCNNClient()
    results, summary = batch_evaluate_grade(
        client, grade=2, page_size=20, max_patients=10, workers=4,
    )
    print("汇总：", summary)
    for r in results[:3]:
        print(r)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    # _demo_url()       # 用 URL
    # _demo_local()     # 用本地图
    _demo_dataset_grades()
    # _demo_batch()
