---
name: imagegen-custom-api
description: Generate or edit raster images using an OpenAI-compatible Images API with user-selected API key sources, Base URLs, and named provider profiles. Use for custom endpoints or configurable image API credentials; not for SVG or code-native graphics.
---

# Imagegen Custom API

This independent derivative of the official imagegen skill uses its bundled CLI through a configurable wrapper. Invoking this skill selects the API workflow; no built-in image tool or additional CLI opt-in is needed. Original system skill files remain unchanged.

## Provider selection

Read [references/configuration.md](references/configuration.md) for configuration and examples. Use `scripts/image_gen.py`, not `image_gen_core.py` directly.

- Honor the user's selected profile, key source, Base URL and model. Reuse a selection established in the conversation.
- Resolve Base URL from `--base-url`, selected profile, `IMAGEGEN_BASE_URL`, `OPENAI_BASE_URL`, then the official OpenAI root. Resolve key source from explicit `--api-key-env` or `--api-key-file`, then profile, then `IMAGEGEN_API_KEY_ENV` or `OPENAI_API_KEY`.
- If the intended custom provider is unknown and no configuration exists, ask for its Base URL and the name of a locally configured key environment variable. Never ask for a secret pasted into chat or print/read its value with tools. An unset selected key source must fail rather than fall back to a different account.
- Credentials are local environment variables or local UTF-8 key files; profiles store references only. Do not include keys in prompts, command arguments, output artifacts or logs.
- This adapter targets OpenAI-compatible Images endpoints. It accepts the official `b64_json` response and compatible `data:image/...` or HTTP(S) image URL responses (URL responses are downloaded before saving). Arbitrary provider protocols and arbitrary model aliases are not supported. Report incompatibility rather than silently switch providers or models.

## Image workflow

1. Classify as generation or editing. For editing, inspect the source and label each input's role. Use only references authorized by the user.
2. Preserve detailed user constraints. Repeat requested composition, crop, pose, background or identity invariants in editing prompts. Read [references/prompting.md](references/prompting.md) when shaping prompts; [references/sample-prompts.md](references/sample-prompts.md) offers optional recipes. Their upstream built-in/fallback routing language does not override this skill's API workflow.
3. Write long prompts to UTF-8 files. Use `generate`, `edit`, or `generate-batch` for distinct JSONL prompts; use `--n` for variants of one prompt. Read [references/cli.md](references/cli.md) for image parameters.
4. Use `--dry-run` when local configuration/payload verification is useful; it requires no SDK, credentials or network and does not validate provider availability. Live calls need the `openai` Python SDK in the task's chosen environment.
5. Preserve the selected model. Default is upstream `gpt-image-2`; transparent output is unsupported for it. Ask before changing to `gpt-image-1.5` unless the user selected it. Provider support for models and parameters is not guaranteed by the default.
6. Save finals to the user's destination or project output directory; scratch prompts and job files belong in the task's scratch directory. Always supply `--out` or `--out-dir`. Use non-overwriting filenames unless replacement is authorized, and inspect images before delivering.
7. Report saved image paths, final prompt (or linked prompt file), selected profile/model and API method. Show images inline when supported.

Do not issue speculative paid calls when creating/configuring the skill. During image tasks, execute authorized calls; stop and report provider incompatibility or authentication errors. Batch retries are bounded by `--max-attempts` (default 3); SDK automatic retries are disabled. Do not launch duplicate jobs after a timeout without checking whether the provider completed the request.

## Maintenance

`scripts/image_gen_core.py` is a verbatim copy of the official CLI; `scripts/image_gen.py` adds connection configuration and response normalization without changing upstream model and image validation. Keep the bundled license. Validate updates with the skill-creator validator and offline tests of config resolution, response shapes, and all three API routes before making real requests.
