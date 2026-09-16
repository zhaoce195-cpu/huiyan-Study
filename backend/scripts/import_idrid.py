"""
IDRiD 多病灶数据集导入命令行脚本
================================

实际逻辑在 app.services.idrid_import_service.run_idrid_import 里，
后台路由 POST /admin/import/idrid 走同一份代码。

使用：
    cd backend
    python scripts/import_idrid.py [--source PATH] [--limit N] [--dry-run] [--no-skip]

幂等：默认 --skip-existing；按 case_no 跳过已存在的病例（仍会追加缺失影像）。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


_THIS = Path(__file__).resolve()
_BACKEND_ROOT = _THIS.parent.parent
if str(_BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(_BACKEND_ROOT))


from app.db.session import SessionLocal
from app.services.idrid_import_service import (  # noqa: E402
    probe_idrid_source,
    resolved_idrid_root,
    run_idrid_import,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="IDRiD 数据集批量导入")
    parser.add_argument(
        "--source",
        default=None,
        help=f"数据集根目录（默认 {resolved_idrid_root()}）",
    )
    parser.add_argument("--limit", type=int, default=None,
                        help="只导入前 N 条（调试用）")
    parser.add_argument("--dry-run", action="store_true",
                        help="只解析不写库")
    parser.add_argument("--no-skip", action="store_true",
                        help="不跳过已存在病例（强制覆盖追加）")
    args = parser.parse_args()

    print(f"源目录：{args.source or resolved_idrid_root()}")
    print(f"limit={args.limit}, dry_run={args.dry_run}, skip_existing={not args.no_skip}")
    probe = probe_idrid_source(args.source)
    print(probe.hint)
    if not probe.ready and not args.dry_run:
        print("约定目录未就绪，中止正式导入。可先 --dry-run 或检查路径。")
        raise SystemExit(2)

    db = SessionLocal()
    try:
        result = run_idrid_import(
            db,
            source_path=args.source,
            limit=args.limit,
            dry_run=args.dry_run,
            skip_existing=not args.no_skip,
        )
        print("\n=== 导入完成 ===")
        print(f"成功病例   : {result.imported_cases}")
        print(f"追加影像   : {result.appended_images}")
        print(f"跳过病例   : {result.skipped_cases}")
        print(f"不完整病例 : {result.incomplete_cases}")
        print(f"耗时       : {result.elapsed_sec}s")
        print(f"DR 等级分布: {result.grade_distribution}")
        if result.sample_case_sns:
            print(f"示例 case_sn: {result.sample_case_sns}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
