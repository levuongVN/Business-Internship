#!/usr/bin/env python3
"""Standalone Gemini connectivity test for the Odoo project.

This script intentionally mirrors the Odoo AI flow:
- read `gemini_api_key` from `odoo.conf` by default
- or read `GEMINI_API_KEY` from environment when provided
- call the same default model used in Odoo (`gemini-2.5-flash-lite`)
- print a masked key and a clear diagnosis for common API failures

Examples:
    python CallAPI.py
    python CallAPI.py --config debian/odoo.conf
    GEMINI_API_KEY=xxx python CallAPI.py --model gemini-1.5-flash
"""

from __future__ import annotations

import argparse
import configparser
import os
import sys
from pathlib import Path

try:
    from google import genai
except Exception as exc:  # pragma: no cover - local runtime dependency
    print("Khong import duoc thu vien `google.genai`.")
    print(f"Chi tiet: {exc}")
    print("Cai dat bang lenh: pip install google-genai")
    raise SystemExit(1) from exc


DEFAULT_CONFIG = "odoo.conf"
DEFAULT_MODEL = "gemini-2.5-flash-lite"
DEFAULT_PROMPT = "Tra ve dung mot tu: ok"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Test ket noi Gemini bang cung config va model voi Odoo.",
    )
    parser.add_argument(
        "--config",
        default=DEFAULT_CONFIG,
        help=f"Duong dan toi file config Odoo. Mac dinh: {DEFAULT_CONFIG}",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Model Gemini can test. Mac dinh: {DEFAULT_MODEL}",
    )
    parser.add_argument(
        "--prompt",
        default=DEFAULT_PROMPT,
        help="Prompt gui toi Gemini.",
    )
    parser.add_argument(
        "--show-key",
        action="store_true",
        help="In day du API key. Khong nen dung neu khong can thiet.",
    )
    return parser.parse_args()


def load_api_key(config_path: Path) -> tuple[str | None, str | None]:
    env_key = os.getenv("GEMINI_API_KEY", "").strip()
    if env_key:
        return env_key.strip('"').strip("'"), None

    parser = configparser.ConfigParser()
    if not config_path.exists():
        return None, f"Khong tim thay file config: {config_path}"

    parser.read(config_path, encoding="utf-8")
    if not parser.has_section("options"):
        return None, f"File {config_path} khong co section [options]"

    value = parser.get("options", "gemini_api_key", fallback="").strip()
    if not value:
        return None, f"File {config_path} chua co bien gemini_api_key"

    return value.strip('"').strip("'"), None


def mask_key(value: str, show_full: bool = False) -> str:
    if show_full:
        return value
    if len(value) <= 14:
        return "*" * len(value)
    return f"{value[:8]}...{value[-6:]}"


def classify_error(message: str) -> str:
    text = (message or "").lower()
    if "429" in text and "resource_exhausted" in text:
        return (
            "Chan doan: het quota Gemini.\n"
            "- API key da duoc doc va request da toi duoc Google.\n"
            "- Loi nay thuong do quota/billing, khong phai do code goi API sai.\n"
            "- Neu doi key nhung van cung project, quota van co the giong nhau."
        )
    if "401" in text or "api key not valid" in text or "invalid api key" in text:
        return "Chan doan: API key sai, bi thu hoi, hoac khong hop le."
    if "403" in text or "permission_denied" in text:
        return "Chan doan: khong du quyen dung model/API nay, hoac billing/project chua dung."
    if "404" in text or "not found" in text:
        return "Chan doan: sai ten model hoac endpoint."
    if "503" in text or "unavailable" in text or "high demand" in text:
        return "Chan doan: model dang qua tai tam thoi. Thu lai sau hoac doi model khac."
    return "Chan doan: loi khong ro rang. Can xem chi tiet response tu Gemini."


def main() -> int:
    args = parse_args()
    config_path = Path(args.config).expanduser().resolve()

    api_key, error = load_api_key(config_path)
    if error:
        print(error)
        return 1

    print("=== Gemini API Test ===")
    print(f"Config dang doc : {config_path}")
    print(f"Model dang test : {args.model}")
    print(f"API key         : {mask_key(api_key, args.show_key)}")
    print(f"Prompt          : {args.prompt}")
    print()

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model=args.model,
            contents=args.prompt,
        )
    except Exception as exc:  # pragma: no cover - depends on remote API
        message = str(exc)
        print("Trang thai      : THAT BAI")
        print(f"Loi goc         : {message}")
        print(classify_error(message))
        return 2

    print("Trang thai      : THANH CONG")
    print(f"Phan hoi        : {getattr(response, 'text', '')!r}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
