#!/usr/bin/env python3
"""Migrate the legacy GitHub image library into Supabase Storage.

This is a one-time, resumable migration. It never deletes source files from
GitHub. Run it from the backend repository, then verify the summary and the
admin image search before removing the old GitHub assets/token.

Examples:
  SUPABASE_URL=... SUPABASE_KEY=... python scripts/migrate_github_image_library_to_supabase.py --dry-run
  SUPABASE_URL=... SUPABASE_KEY=... python scripts/migrate_github_image_library_to_supabase.py
  ... python scripts/migrate_github_image_library_to_supabase.py --owner mahabucha --owner muteteam
"""
from __future__ import annotations

import argparse
import mimetypes
import os
import sys
from dataclasses import dataclass
from pathlib import PurePosixPath
from urllib.parse import quote

import requests

OWNERS = ("mahabucha", "muteteam", "muteteam_ceremony", "laos", "ratchaprasong")
BUCKET = "portfolio"
LIBRARY_PREFIX = "image-library"
TIMEOUT = (15, 120)


@dataclass
class Summary:
    discovered: int = 0
    copied: int = 0
    failed: int = 0


def env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"ไม่ได้ตั้งค่า environment variable: {name}")
    return value


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Move legacy GitHub image-library files into Supabase Storage.")
    parser.add_argument("--owner", action="append", choices=OWNERS, help="ย้ายเฉพาะเพจที่ระบุ (เลือกซ้ำได้)")
    parser.add_argument("--dry-run", action="store_true", help="ตรวจรายการโดยไม่อัปโหลด")
    parser.add_argument("--continue-on-error", action="store_true", help="เก็บ error แล้วทำไฟล์ถัดไป")
    return parser.parse_args()


def github_headers() -> dict[str, str]:
    token = os.getenv("GITHUB_TOKEN", "").strip()
    return {"Authorization": f"Bearer {token}"} if token else {}


def storage_headers(key: str) -> dict[str, str]:
    return {"apikey": key, "Authorization": f"Bearer {key}"}


def safe_filename(value: str) -> str:
    path = PurePosixPath(value)
    if not value or path.name != value or value in {".", ".."}:
        raise ValueError(f"ชื่อไฟล์จากต้นทางไม่ปลอดภัย: {value!r}")
    return value


def list_legacy_files(session: requests.Session, *, github_user: str, repo: str, branch: str, owner: str) -> list[dict]:
    url = f"https://api.github.com/repos/{github_user}/{repo}/contents/images/{owner}?ref={quote(branch)}"
    response = session.get(url, headers=github_headers(), timeout=TIMEOUT)
    if response.status_code == 404:
        print(f"[{owner}] ไม่พบโฟลเดอร์บน GitHub — ข้าม")
        return []
    response.raise_for_status()
    return [
        item for item in response.json()
        if item.get("type") == "file" and item.get("name") != ".keep"
    ]


def upload_file(
    session: requests.Session,
    *, base_url: str,
    service_key: str,
    owner: str,
    item: dict,
    dry_run: bool,
) -> None:
    filename = safe_filename(str(item.get("name", "")))
    destination = f"{LIBRARY_PREFIX}/{owner}/{filename}"
    if dry_run:
        print(f"[dry-run] {destination}")
        return

    source_url = item.get("download_url")
    if not source_url:
        raise RuntimeError(f"ไม่มี download_url สำหรับ {filename}")
    source = session.get(source_url, headers=github_headers(), timeout=TIMEOUT)
    source.raise_for_status()
    content_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
    response = session.post(
        f"{base_url}/storage/v1/object/{BUCKET}/{quote(destination)}",
        data=source.content,
        headers={**storage_headers(service_key), "Content-Type": content_type, "x-upsert": "true"},
        timeout=TIMEOUT,
    )
    if not response.ok:
        raise RuntimeError(f"Supabase Storage ตอบ {response.status_code}: {response.text[:500]}")
    print(f"[copied] {destination}")


def main() -> int:
    args = parse_args()
    try:
        base_url = env("SUPABASE_URL").rstrip("/")
        service_key = env("SUPABASE_KEY")
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2

    github_user = os.getenv("GITHUB_USERNAME", "mrtharatoy")
    repo = os.getenv("REPO_NAME", "siamganesh-online-backend")
    branch = os.getenv("BRANCH", "main")
    selected_owners = args.owner or OWNERS
    summary = Summary()

    print(f"Source: GitHub {github_user}/{repo}@{branch}")
    print(f"Destination: Supabase {BUCKET}/{LIBRARY_PREFIX}/<owner>/")
    if args.dry_run: print("Mode: dry-run (ไม่มีการเขียนไฟล์)")

    with requests.Session() as session:
        for owner in selected_owners:
            try:
                files = list_legacy_files(session, github_user=github_user, repo=repo, branch=branch, owner=owner)
            except requests.RequestException as error:
                print(f"[{owner}] ERROR อ่านรายการไม่ได้: {error}", file=sys.stderr)
                summary.failed += 1
                if not args.continue_on_error: break
                continue
            summary.discovered += len(files)
            for item in files:
                try:
                    upload_file(session, base_url=base_url, service_key=service_key, owner=owner, item=item, dry_run=args.dry_run)
                    summary.copied += 1
                except (requests.RequestException, RuntimeError, ValueError) as error:
                    summary.failed += 1
                    print(f"[{owner}] ERROR {item.get('name', '?')}: {error}", file=sys.stderr)
                    if not args.continue_on_error: break
            if summary.failed and not args.continue_on_error: break

    print(f"\nสรุป: พบ {summary.discovered} ไฟล์ | {'ตรวจ' if args.dry_run else 'ย้าย'} สำเร็จ {summary.copied} | ผิดพลาด {summary.failed}")
    return 1 if summary.failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
