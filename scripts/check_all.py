# -*- coding: utf-8 -*-
"""
提交前统一检查

把这套项目里已经建立起来的门禁收在一条命令里。分散在各处、要靠人记得
去跑的检查，等同于没有 —— 前端类型检查攒到 48 个错误才被清理一次，
就是这么来的。

    python scripts/check_all.py            # 全部（需要服务在跑的项会自动跳过）
    python scripts/check_all.py --quick    # 只跑不依赖外部服务的项

各项含义：
    后端测试        pytest
    数据库一致性    迁移链与建库路径体检（含当前库的模型漂移）
    前端类型检查    必须为 0 —— 这是唯一能挡住「孤儿代码」的自动手段
    前端构建        类型过了不代表能打包
    阅片内核自检    需要 vite 在 5178；坐标算错、影像没解码都能通过编译
    PACS 对照巡检   需要 Orthanc；失配意味着 DICOM 能力正在静默降级
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
PY = BACKEND / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = BACKEND / ".venv" / "bin" / "python"
if not PY.exists():
    PY = Path(sys.executable)


def run(cmd, cwd, shell=False):
    t0 = time.time()
    p = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True,
                       encoding="utf-8", errors="replace", shell=shell)
    return p.returncode, (p.stdout or "") + (p.stderr or ""), time.time() - t0


def service_up(url: str) -> bool:
    import urllib.request

    try:
        urllib.request.urlopen(url, timeout=3)
        return True
    except Exception:
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--quick", action="store_true",
                    help="跳过依赖外部服务的检查")
    args = ap.parse_args()

    results = []

    def gate(name, ok, detail="", secs=0.0, skipped=False):
        results.append((name, ok, skipped))
        mark = "—" if skipped else ("✓" if ok else "✗")
        tail = f"  [{secs:.0f}s]" if secs >= 1 else ""
        print(f"{mark} {name}{tail}")
        if detail:
            for line in detail.strip().splitlines()[-6:]:
                print("    " + line[:160])

    print("=" * 66)

    # 后端测试
    code, out, secs = run([str(PY), "-m", "pytest", "tests/", "-q"], BACKEND)
    passed = next((l for l in out.splitlines() if "passed" in l), "")
    gate("后端测试", code == 0, "" if code == 0 else out, secs)
    if code == 0 and passed:
        print(f"    {passed.strip()}")

    # 数据库一致性
    code, out, secs = run([str(PY), "scripts/check_migration_chain.py"], BACKEND)
    gate("数据库一致性（迁移链 / 建库路径 / 模型漂移）", code == 0,
         "" if code == 0 else out, secs)

    # 前端类型检查
    code, out, secs = run(["npx", "vue-tsc", "-p", "tsconfig.app.json", "--noEmit"],
                          FRONTEND, shell=True)
    errs = [l for l in out.splitlines() if "error TS" in l]
    gate(f"前端类型检查（{len(errs)} 个错误，必须为 0）", not errs,
         "\n".join(errs[:6]), secs)

    # 前端构建
    code, out, secs = run(["npx", "vite", "build"], FRONTEND, shell=True)
    gate("前端构建", code == 0, "" if code == 0 else out, secs)

    # 阅片内核自检（需 vite）
    if args.quick:
        gate("阅片内核自检", True, "", 0, skipped=True)
    elif service_up("http://127.0.0.1:5178/"):
        # 前一步的 vite build 会让 dev server 重新预构建依赖，
        # 紧接着跑会拿到还没就绪的模块，表现为 WebGL 报
        # 「Cannot read properties of null」。这是环境时序问题，不是回归。
        #
        # 重试而不是直接判失败：一个会随机变红的门禁，
        # 很快就会被所有人当成噪音忽略掉，那还不如没有。
        code, out, secs = 1, "", 0.0
        for attempt in range(3):
            if attempt:
                time.sleep(4)
            code, out, secs = run(["node", "scripts/check_station.mjs", "5178"],
                                  FRONTEND, shell=True)
            if code == 0:
                break
        gate("阅片内核自检", code == 0, "" if code == 0 else out, secs)
    else:
        gate("阅片内核自检（vite 未在 5178 运行）", True, "", 0, skipped=True)

    # PACS 对照巡检（需 Orthanc）
    if args.quick:
        gate("PACS 对照巡检", True, "", 0, skipped=True)
    else:
        code, out, secs = run([str(PY), "scripts/link_dicom_instances.py"], BACKEND)
        if "PACS 不可达" in out and "不可达       0" not in out:
            gate("PACS 对照巡检（PACS 不可达）", True, "", secs, skipped=True)
        else:
            gate("PACS 对照巡检", code == 0,
                 "" if code == 0 else out, secs)

    print("-" * 66)
    failed = [n for n, ok, sk in results if not ok and not sk]
    skipped = [n for n, ok, sk in results if sk]
    if skipped:
        print(f"跳过 {len(skipped)} 项（依赖的服务未运行）")
    print("全部通过" if not failed else f"未通过：{'、'.join(failed)}")
    print("=" * 66)
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
