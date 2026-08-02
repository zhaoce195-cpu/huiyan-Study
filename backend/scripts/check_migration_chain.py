# -*- coding: utf-8 -*-
"""
迁移与建库路径体检

对应遗留清单 D-004。

本项目有两条路径，二者必须产出同一套结构，否则新装的库和升级上来的库
会长得不一样 —— 这种差异往往要到某个接口在一边能跑、另一边报
「no such column」时才被发现：

    全新部署   create_all() + alembic stamp head
    升级已有库 alembic upgrade head（只跑增量）

本脚本做三件事：
    1. 空库上 bootstrap，确认建得起来（现在从零建库是否真的可行）；
    2. 对 bootstrap 出来的库跑 alembic check，确认模型与库无漂移
       —— 有漂移说明改了模型却没写迁移；
    3. 空库上直接 upgrade 必须被明确拦住，而不是报「no such table」。

用法：
    python scripts/check_migration_chain.py
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BACKEND = Path(__file__).resolve().parent.parent


def _run(args, db_path):
    env = dict(os.environ)
    env["SQLITE_PATH"] = str(db_path)
    env["DB_TYPE"] = "sqlite"
    return subprocess.run(
        args, cwd=str(BACKEND), env=env,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


def main() -> int:
    tmp = Path(tempfile.mkdtemp())
    checks = []

    def check(name, ok, detail=""):
        checks.append(ok)
        print(f"{'✓' if ok else '✗'} {name}{('  —— ' + detail) if detail else ''}")
        return ok

    print("=" * 64)

    # 1) 空库能否 bootstrap
    fresh = tmp / "fresh.db"
    r = _run([sys.executable, "scripts/bootstrap_db.py"], fresh)
    ok = r.returncode == 0 and fresh.exists()
    check("空库可 bootstrap（create_all + stamp）", ok,
          "" if ok else (r.stdout + r.stderr)[-400:])
    if not ok:
        print("=" * 64)
        return 1

    from sqlalchemy import create_engine, inspect

    eng = create_engine(f"sqlite:///{fresh}")
    tables = set(inspect(eng).get_table_names())
    eng.dispose()
    check("已纳入 alembic 管理", "alembic_version" in tables,
          f"共 {len(tables)} 张表")

    # 2) 模型与库是否漂移
    r = _run([sys.executable, "-m", "alembic", "check"], fresh)
    drift = r.returncode != 0
    check("模型与迁移无漂移", not drift,
          "" if not drift else (r.stdout + r.stderr).strip()[-400:])

    # 3) 空库直跑 upgrade 必须被拦住并说清原因
    empty = tmp / "empty.db"
    r = _run([sys.executable, "-m", "alembic", "upgrade", "head"], empty)
    out = r.stdout + r.stderr
    guarded = r.returncode != 0 and "bootstrap_db.py" in out
    check("空库直跑 upgrade 被明确拦截", guarded,
          "" if guarded else out.strip()[-300:])

    # 4) 当前配置的库（开发库/存量库）也要无漂移。
    #    只验新建的库等于没验 —— 新库是 create_all 出来的，
    #    天然与模型一致，那条检查永远为真。真正会出问题的是
    #    一路升级上来的库。
    r = subprocess.run(
        [sys.executable, "-m", "alembic", "check"],
        cwd=str(BACKEND), capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    ok = r.returncode == 0
    check("当前配置的库与模型无漂移", ok,
          "" if ok else (r.stdout + r.stderr).strip()[-300:])

    print("-" * 64)
    failed = checks.count(False)
    print("全部通过" if not failed else f"{failed} 项未通过")
    print("=" * 64)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
