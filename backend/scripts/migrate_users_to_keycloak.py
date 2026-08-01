# -*- coding: utf-8 -*-
"""
存量用户迁移到 Keycloak

对应方案第 8.2 节「用户与权限迁移」与报告 P0（认证安全整改）。

关于密码
    平台现有密码是 bcrypt 哈希，而 Keycloak 原生只支持 pbkdf2 系列，
    无法直接导入。因此迁移后用户必须重设密码——这与报告要求的
    「首次登录强制改密」恰好一致，不是妥协而是顺势落实。

    每个用户会被设置一个临时密码并附带 UPDATE_PASSWORD 必需动作，
    首次登录时 Keycloak 会强制其修改。

用法：
    # 预演
    python scripts/migrate_users_to_keycloak.py

    # 实际迁移
    python scripts/migrate_users_to_keycloak.py --apply

    # 指定 Keycloak
    python scripts/migrate_users_to_keycloak.py --apply \
        --kc http://localhost:8085 --realm huiyan \
        --admin-user admin --admin-password admin
"""

import argparse
import json
import secrets
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import create_engine  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402

from app.db.models import User  # noqa: E402

# 平台角色 → Keycloak realm 角色（同名，一一对应）
VALID_ROLES = {"STUDENT", "TEACHER", "ADMIN", "PATIENT"}


def _req(url, token=None, method="GET", body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.Request(url, data=data, method=method)
    r.add_header("Content-Type", "application/json")
    if token:
        r.add_header("Authorization", "Bearer " + token)
    with urllib.request.urlopen(r, timeout=30) as resp:
        raw = resp.read()
        return resp.status, (json.loads(raw) if raw else None)


def admin_token(kc, admin_user, admin_password):
    data = urllib.parse.urlencode({
        "grant_type": "password", "client_id": "admin-cli",
        "username": admin_user, "password": admin_password,
    }).encode()
    r = urllib.request.Request(
        f"{kc}/realms/master/protocol/openid-connect/token",
        data=data, method="POST")
    r.add_header("Content-Type", "application/x-www-form-urlencoded")
    with urllib.request.urlopen(r, timeout=30) as resp:
        return json.load(resp)["access_token"]


def build_session(db_url: str):
    return sessionmaker(bind=create_engine(db_url, future=True),
                        autoflush=False, future=True)()


def resolve_db_url(explicit=""):
    if explicit:
        return explicit
    try:
        from app.core.config import settings
        return str(settings.DATABASE_URL)
    except Exception:
        return f"sqlite:///{(Path(__file__).resolve().parent.parent / 'edu_eye.db').as_posix()}"


def main() -> int:
    p = argparse.ArgumentParser(description="把存量用户迁移到 Keycloak")
    p.add_argument("--apply", action="store_true")
    p.add_argument("--db", default="")
    p.add_argument("--kc", default="http://localhost:8085")
    p.add_argument("--realm", default="huiyan")
    p.add_argument("--admin-user", default="admin")
    p.add_argument("--admin-password", default="admin")
    p.add_argument("--skip-demo", action="store_true",
                   help="跳过 admin/teacher/student 这三个演示账号")
    args = p.parse_args()

    kc = args.kc.rstrip("/")
    base = f"{kc}/admin/realms/{args.realm}"

    print(f"数据库　：{resolve_db_url(args.db)}")
    print(f"Keycloak：{kc}  realm={args.realm}")
    print(f"模式　　：{'实际迁移' if args.apply else '预演（不写入）'}")
    print("-" * 70)

    session = build_session(resolve_db_url(args.db))
    try:
        users = session.query(User).order_by(User.id).all()
        rows = []
        for u in users:
            role = (u.role.code if u.role else "") or ""
            rows.append({
                "username": u.username,
                "realName": u.real_name or "",
                # Keycloak 24+ 要求 email 必填，缺失时按用户名合成占位地址
                "email": u.email or f"{u.username}@huiyan.local",
                "emailSynthesized": not bool(u.email),
                "role": role if role in VALID_ROLES else "",
                "enabled": bool(u.is_active),
            })
    finally:
        session.close()

    print(f"待迁移用户 {len(rows)} 个：")
    for r in rows:
        mark = "  ← email 为合成占位" if r["emailSynthesized"] else ""
        print(f"  {r['username']:<16} {r['realName']:<10} "
              f"{r['role'] or '(无角色)':<8} enabled={r['enabled']}{mark}")

    no_role = [r for r in rows if not r["role"]]
    if no_role:
        print(f"\n注意：{len(no_role)} 个用户没有可映射的角色，"
              f"迁移后仅有默认角色：{[r['username'] for r in no_role]}")

    if not args.apply:
        print("-" * 70)
        print("预演结束，未写入 Keycloak。确认后加 --apply 执行。")
        return 0

    try:
        tok = admin_token(kc, args.admin_user, args.admin_password)
    except Exception as exc:
        print(f"无法获取 Keycloak 管理令牌：{exc}", file=sys.stderr)
        return 1

    # realm 角色 id 映射
    _, realm_roles = _req(f"{base}/roles", tok)
    role_map = {r["name"]: r for r in realm_roles}

    created = updated = failed = 0
    temp_passwords = []

    for r in rows:
        payload = {
            "username": r["username"],
            "enabled": r["enabled"],
            "email": r["email"],
            "emailVerified": True,
            "firstName": r["realName"][:1] or r["username"][:1],
            "lastName": r["realName"][1:] or "",
            # 密码无法从 bcrypt 迁移，强制首登改密（报告 P0）
            "requiredActions": ["UPDATE_PASSWORD"],
        }
        try:
            status, _ = _req(f"{base}/users", tok, method="POST", body=payload)
            created += 1
        except urllib.error.HTTPError as e:
            if e.code == 409:      # 已存在 → 更新
                _, found = _req(
                    f"{base}/users?username={urllib.parse.quote(r['username'])}&exact=true",
                    tok)
                if not found:
                    failed += 1
                    continue
                uid = found[0]["id"]
                merged = {**found[0], **payload}
                _req(f"{base}/users/{uid}", tok, method="PUT", body=merged)
                updated += 1
            else:
                failed += 1
                print(f"  {r['username']} 迁移失败：HTTP {e.code}", file=sys.stderr)
                continue

        # 取回 id 并设角色 + 临时密码
        _, found = _req(
            f"{base}/users?username={urllib.parse.quote(r['username'])}&exact=true", tok)
        if not found:
            continue
        uid = found[0]["id"]

        if r["role"] and r["role"] in role_map:
            role = role_map[r["role"]]
            _req(f"{base}/users/{uid}/role-mappings/realm", tok, method="POST",
                 body=[{"id": role["id"], "name": role["name"]}])

        temp = "Huiyan@" + secrets.token_hex(4)
        _req(f"{base}/users/{uid}/reset-password", tok, method="PUT",
             body={"type": "password", "value": temp, "temporary": True})
        temp_passwords.append((r["username"], temp))

    print("-" * 70)
    print(f"新建 {created}　更新 {updated}　失败 {failed}")

    if temp_passwords:
        out = Path("keycloak-temp-passwords.txt")
        out.write_text(
            "用户名\t临时密码（首次登录须修改）\n" +
            "\n".join(f"{u}\t{p}" for u, p in temp_passwords),
            encoding="utf-8")
        print(f"\n临时密码已写入 {out.resolve()}")
        print("请通过安全渠道分发给对应用户，分发后删除该文件。")
        print("所有用户首次登录都会被 Keycloak 强制修改密码。")

    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
