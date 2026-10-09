#!/usr/bin/env python3
"""Configurable endpoint wrapper around the bundled official image CLI.

The upstream image_gen_core.py is preserved verbatim. No API key is persisted.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
import math
import base64
from types import SimpleNamespace
from urllib.request import Request, urlopen
from urllib.parse import urlsplit

import image_gen_core as core

DEFAULT_URL = "https://api.openai.com/v1"


def _normalize_image_result(result, options):
    """Normalize OpenAI b64_json and compatible URL/data-URI responses."""
    data = getattr(result, "data", None)
    if not isinstance(data, list):
        raise TypeError("Images response has no data list")
    normalized = []
    for item in data:
        encoded = getattr(item, "b64_json", None)
        if encoded:
            normalized.append(SimpleNamespace(b64_json=encoded))
            continue
        url = getattr(item, "url", None)
        if isinstance(url, str) and url.startswith("data:image/") and "," in url:
            encoded = url.split(",", 1)[1]
            normalized.append(SimpleNamespace(b64_json=encoded))
            continue
        if isinstance(url, str) and url.startswith(("https://", "http://")):
            request = Request(url, headers={"User-Agent": "imagegen-custom-api"})
            with urlopen(request, timeout=options["timeout"]) as response:
                normalized.append(SimpleNamespace(b64_json=base64.b64encode(response.read()).decode("ascii")))
            continue
        raise TypeError("Images response item has neither b64_json nor a supported URL")
    return SimpleNamespace(data=normalized)


class _ImagesProxy:
    def __init__(self, images, options):
        self._images = images
        self._options = options

    def generate(self, **kwargs):
        return _normalize_image_result(self._images.generate(**kwargs), self._options)

    def edit(self, **kwargs):
        return _normalize_image_result(self._images.edit(**kwargs), self._options)


class _AsyncImagesProxy:
    def __init__(self, images, options):
        self._images = images
        self._options = options

    async def generate(self, **kwargs):
        result = await self._images.generate(**kwargs)
        return _normalize_image_result(result, self._options)

    async def edit(self, **kwargs):
        result = await self._images.edit(**kwargs)
        return _normalize_image_result(result, self._options)


class _ClientProxy:
    def __init__(self, client, options):
        self._client = client
        self.images = _ImagesProxy(client.images, options)


class _AsyncClientProxy:
    def __init__(self, client, options):
        self._client = client
        self.images = _AsyncImagesProxy(client.images, options)


def resolve_config(args):
    profile = {}
    if args.profile:
        config_path = Path(args.config).expanduser()
        data = json.loads(config_path.read_text(encoding="utf-8-sig"))
        profile = data.get("profiles", {}).get(args.profile)
        if not isinstance(profile, dict):
            raise ValueError("Selected profile does not exist or is not an object.")
        if "api_key" in profile:
            raise ValueError("Store an api_key_env or api_key_file reference, not an api_key in profiles.")
    base_url = args.base_url or profile.get("base_url") or os.getenv("IMAGEGEN_BASE_URL") or os.getenv("OPENAI_BASE_URL") or DEFAULT_URL
    parsed = urlsplit(base_url)
    if parsed.scheme not in ("https", "http") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Base URL must be an HTTP(S) API root without credentials, query or fragment.")
    if parsed.path.rstrip("/").endswith(("/images/generations", "/images/edits")):
        raise ValueError("Use the API root (usually ending in /v1), not an images endpoint.")
    # An explicit selector overrides both selectors from the profile.
    key_file = args.api_key_file
    key_env = args.api_key_env
    if not key_file and not key_env:
        key_file = profile.get("api_key_file")
        key_env = profile.get("api_key_env")
        if key_file and key_env:
            raise ValueError("Profile must select only one of api_key_file and api_key_env.")
        if key_file:
            path = Path(key_file).expanduser()
            key_file = str(path if path.is_absolute() else config_path.parent / path)
    key_env = key_env or os.getenv("IMAGEGEN_API_KEY_ENV") or "OPENAI_API_KEY"
    secret = None
    if not args.wrapper_dry_run:
        secret = Path(key_file).expanduser().read_text(encoding="utf-8-sig").strip() if key_file else os.getenv(key_env, "").strip()
        if not secret:
            raise ValueError("Selected API key source is empty or unset. Configure it locally before running.")
    timeout = args.timeout if args.timeout is not None else profile.get("timeout", 180)
    timeout = float(timeout)
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError("Timeout must be positive.")
    return {"api_key": secret, "base_url": base_url.rstrip("/") + "/", "timeout": timeout, "max_retries": 0}, profile.get("model")


def main(argv=None):
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("--profile")
    parser.add_argument("--config", default=str(Path(__file__).resolve().parents[1] / "profiles.json"))
    parser.add_argument("--base-url")
    key_group = parser.add_mutually_exclusive_group()
    key_group.add_argument("--api-key-env")
    key_group.add_argument("--api-key-file")
    parser.add_argument("--timeout", type=float)
    args, remaining = parser.parse_known_args(argv)
    if not remaining or "--help" in remaining or "-h" in remaining:
        parser.print_help()
        print("\nUpstream image options:")
        saved = sys.argv
        try:
            sys.argv = [saved[0], *(remaining or ["--help"])]
            return core.main()
        finally:
            sys.argv = saved
    args.wrapper_dry_run = "--dry-run" in remaining
    try:
        options, model = resolve_config(args)
    except (ValueError, OSError, TypeError) as exc:
        # Config contents and credential paths are deliberately not echoed.
        print(f"Configuration error ({type(exc).__name__}). Check profile, URL, timeout and key source.", file=sys.stderr)
        return 2
    if model and not any(v == "--model" or v.startswith("--model=") for v in remaining):
        remaining.extend(["--model", model])

    def create_client(asynchronous=False):
        try:
            from openai import OpenAI, AsyncOpenAI
        except ImportError:
            core._die("Missing openai SDK. Install with: python -m pip install openai")
        client = (AsyncOpenAI if asynchronous else OpenAI)(**options)
        return _AsyncClientProxy(client, options) if asynchronous else _ClientProxy(client, options)

    saved_argv = sys.argv
    saved_stderr = sys.stderr

    class RedactedStderr:
        def write(self, value):
            secret = options["api_key"]
            return saved_stderr.write(value.replace(secret, "[REDACTED]") if secret else value)

        def flush(self):
            saved_stderr.flush()

    sys.stderr = RedactedStderr()
    saved_functions = (core._ensure_api_key, core._create_client, core._create_async_client)
    core._ensure_api_key = lambda dry_run: None
    core._create_client = lambda: create_client()
    core._create_async_client = lambda: create_client(True)
    sys.argv = [saved_argv[0], *remaining]
    try:
        print(f"Image API root: {options['base_url']} (key value hidden)", file=sys.stderr)
        return core.main()
    except SystemExit as exc:
        return int(exc.code or 0)
    except Exception as exc:
        # Avoid provider errors/tracebacks echoing credentials or request headers.
        status = getattr(exc, "status_code", None)
        print(f"Image request failed: {type(exc).__name__}" + (f" (HTTP {status})" if status else "") + ". Check provider compatibility and configuration.", file=sys.stderr)
        return 1
    finally:
        sys.stderr = saved_stderr
        sys.argv = saved_argv
        core._ensure_api_key, core._create_client, core._create_async_client = saved_functions


if __name__ == "__main__":
    raise SystemExit(main())
