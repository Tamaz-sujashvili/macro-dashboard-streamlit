#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path


DATASET_SLUG = "pakkanmeric/bloomberg-data"


def _find_kaggle_exe() -> str | None:
    exe = shutil.which("kaggle")
    if exe:
        return exe
    # Common install location for `pip install --user kaggle` on macOS
    fallback = Path.home() / "Library" / "Python" / "3.10" / "bin" / "kaggle"
    if fallback.exists():
        return str(fallback)
    return None


def _require_kaggle_json() -> Path:
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    if not kaggle_json.exists():
        print("Missing Kaggle credentials:", file=sys.stderr)
        print(f"  Expected: {kaggle_json}", file=sys.stderr)
        print("", file=sys.stderr)
        print("Fix:", file=sys.stderr)
        print("  1) Kaggle -> Account -> Settings -> API -> Create New API Token", file=sys.stderr)
        print(f"  2) Move kaggle.json to: {kaggle_json}", file=sys.stderr)
        print("  3) chmod 600 ~/.kaggle/kaggle.json", file=sys.stderr)
        raise SystemExit(2)

    # Quick sanity: ensure it parses + has expected keys
    try:
        data = json.loads(kaggle_json.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"Invalid JSON in {kaggle_json}: {e}", file=sys.stderr)
        raise SystemExit(2)

    if not isinstance(data, dict) or "username" not in data or "key" not in data:
        print(f"Unexpected format in {kaggle_json} (expected keys: username, key).", file=sys.stderr)
        raise SystemExit(2)

    return kaggle_json


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    proc = subprocess.run(cmd, cwd=str(cwd) if cwd else None)
    if proc.returncode != 0:
        raise SystemExit(proc.returncode)


def _unzip_all(download_dir: Path, extract_dir: Path) -> list[Path]:
    zips = sorted(download_dir.glob("*.zip"))
    extracted: list[Path] = []
    for z in zips:
        with zipfile.ZipFile(z, "r") as zf:
            for member in zf.namelist():
                # Skip directory entries
                if member.endswith("/"):
                    continue
                out_path = extract_dir / member
                out_path.parent.mkdir(parents=True, exist_ok=True)
                zf.extract(member, path=extract_dir)
                extracted.append(out_path)
    return extracted


def _preview_data(extract_dir: Path) -> None:
    # Prefer CSV; fall back to parquet; otherwise just list files.
    files = [p for p in extract_dir.rglob("*") if p.is_file()]
    if not files:
        print(f"No extracted files found in: {extract_dir}")
        return

    print("")
    print("Extracted files (first 25):")
    for p in files[:25]:
        rel = p.relative_to(extract_dir)
        size = p.stat().st_size
        print(f"  {rel} ({size} bytes)")
    if len(files) > 25:
        print(f"  ... ({len(files) - 25} more)")

    csvs = [p for p in files if p.suffix.lower() == ".csv"]
    parqs = [p for p in files if p.suffix.lower() in {".parquet", ".pq"}]
    excels = [p for p in files if p.suffix.lower() in {".xlsx", ".xls"}]
    target = csvs[0] if csvs else (parqs[0] if parqs else (excels[0] if excels else None))
    if not target:
        return

    try:
        import pandas as pd  # type: ignore
    except Exception as e:  # noqa: BLE001
        print(f"\nFound data file {target.name} but pandas isn't available: {e}")
        return

    print("")
    print(f"Preview: {target.relative_to(extract_dir)}")
    try:
        if target.suffix.lower() == ".csv":
            df = pd.read_csv(target, nrows=5)
        elif target.suffix.lower() in {".parquet", ".pq"}:
            df = pd.read_parquet(target).head(5)
        else:
            # Excel files need openpyxl (xlsx) or xlrd (xls); keep this optional.
            df = pd.read_excel(target).head(5)
        print("Columns:", list(df.columns))
        print(df.to_string(index=False))
    except Exception as e:  # noqa: BLE001
        print(f"Failed to read {target.name}: {e}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=DATASET_SLUG)
    ap.add_argument("--download-dir", default=str(Path(__file__).resolve().parent / "download"))
    ap.add_argument("--extract-dir", default=str(Path(__file__).resolve().parent / "data"))
    ap.add_argument("--no-download", action="store_true", help="Skip download and only unzip/preview existing zips.")
    args = ap.parse_args()

    kaggle_exe = _find_kaggle_exe()
    if not kaggle_exe:
        print("Kaggle CLI not found.", file=sys.stderr)
        print("Install:", file=sys.stderr)
        print("  python3 -m pip install --user kaggle", file=sys.stderr)
        raise SystemExit(2)

    # Kaggle will refuse without credentials; check early with a useful error.
    _require_kaggle_json()

    download_dir = Path(args.download_dir).expanduser().resolve()
    extract_dir = Path(args.extract_dir).expanduser().resolve()
    download_dir.mkdir(parents=True, exist_ok=True)
    extract_dir.mkdir(parents=True, exist_ok=True)

    if not args.no_download:
        print(f"Downloading {args.dataset} ...")
        _run([kaggle_exe, "datasets", "download", "-d", args.dataset, "-p", str(download_dir), "--force"])

    print("Unzipping ...")
    extracted = _unzip_all(download_dir, extract_dir)
    if extracted:
        print(f"Extracted {len(extracted)} files into: {extract_dir}")
    else:
        print(f"No zip files found in: {download_dir}")

    _preview_data(extract_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
