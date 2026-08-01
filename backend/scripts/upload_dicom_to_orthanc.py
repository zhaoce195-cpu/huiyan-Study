# -*- coding: utf-8 -*-
"""
把转换好的 DICOM 实例推送到 Orthanc

对应方案第 8.1 节「影像迁移」第 5 步：
    STOW-RS 批量入 Orthanc，转换后逐例校验眼别、张数、可打开性，
    失败清单人工复核。

用法：
    # 预演：只统计，不上传
    python scripts/upload_dicom_to_orthanc.py

    # 实际上传
    python scripts/upload_dicom_to_orthanc.py --apply

    # 指定服务地址与凭据
    python scripts/upload_dicom_to_orthanc.py --apply \
        --url http://localhost:8042 --user huiyan --password xxx
"""

import argparse
import sys
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import requests  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser(description="批量推送 DICOM 到 Orthanc")
    p.add_argument("--dir", default="app/static/dicom", help="DICOM 目录")
    p.add_argument("--url", default="http://localhost:8042", help="Orthanc 地址")
    p.add_argument("--user", default="", help="（已弃用）Orthanc 现由 Keycloak 鉴权")
    p.add_argument("--password", default="", help="（已弃用）")
    p.add_argument("--apply", action="store_true", help="实际上传；不加则预演")
    args = p.parse_args()

    root = Path(args.dir)
    if not root.is_dir():
        print(f"目录不存在：{root}", file=sys.stderr)
        return 1

    files = sorted(root.rglob("*.dcm"))

    # Orthanc 已改为纯 Keycloak 鉴权（AuthenticationEnabled=false），
    # 这里复用后端的服务账号令牌，不再使用静态口令。
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from app.services.dicomweb_client import _service_account_token

    def headers(content_type=None):
        h = {"Authorization": f"Bearer {_service_account_token()}"}
        if content_type:
            h["Content-Type"] = content_type
        return h

    print(f"源目录　：{root}")
    print(f"Orthanc ：{args.url}")
    print(f"实例数　：{len(files)}")
    print(f"模式　　：{'实际上传' if args.apply else '预演（不上传）'}")
    print("-" * 66)

    if not args.apply:
        total = sum(f.stat().st_size for f in files)
        print(f"待上传合计 {total / 1048576:.1f} MB")
        print("预演结束。确认后加 --apply 执行。")
        return 0

    # 连通性与鉴权先探一次，避免逐个文件失败刷屏
    try:
        r = requests.get(f"{args.url}/system", headers=headers(), timeout=15)
        r.raise_for_status()
    except Exception as exc:
        print(f"无法连接 Orthanc：{exc}", file=sys.stderr)
        return 1

    ok = failed = 0
    problems = []
    for f in files:
        try:
            # 单实例走 /instances（等价于 STOW-RS 的单帧上传，语义更直接）
            resp = requests.post(
                f"{args.url}/instances",
                data=f.read_bytes(),
                headers=headers("application/dicom"),
                timeout=120,
            )
            if resp.status_code in (200, 409):
                ok += 1
            else:
                failed += 1
                problems.append(f"{f.name}: HTTP {resp.status_code} {resp.text[:120]}")
        except Exception as exc:
            failed += 1
            problems.append(f"{f.name}: {exc}")

    print(f"上传成功：{ok}")
    print(f"上传失败：{failed}")
    if problems:
        print("-" * 66)
        for x in problems[:20]:
            print(f"  {x}")
        if len(problems) > 20:
            print(f"  ... 另有 {len(problems) - 20} 条")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
