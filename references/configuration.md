# API configuration

The wrapper supports official image CLI options plus `--profile`, `--config`, `--base-url`, `--api-key-env`, `--api-key-file`, and `--timeout`. Wrapper options work before or after the subcommand. Keys themselves are never command arguments.

Base URL is the API root, often ending in `/v1`; the SDK adds `/images/generations` or `/images/edits`. Use the exact root required by your provider, not the full endpoint. HTTPS and local HTTP roots are accepted; do not embed credentials, query or fragment in the URL.

## Per-call selection (PowerShell)

Configure `MY_IMAGE_API_KEY` locally through your environment settings or secret manager. Restart the calling process if needed to inherit changes. Do not paste the key into chat.

```powershell
$imageCli = Join-Path $env:USERPROFILE '.codex\skills\imagegen-custom-api\scripts\image_gen.py'
python $imageCli generate --base-url 'https://your-provider.example/v1' --api-key-env MY_IMAGE_API_KEY --prompt 'Blue underwater anime illustration' --out 'outputs\blue-anime.png'
python $imageCli edit --base-url 'https://your-provider.example/v1' --api-key-env MY_IMAGE_API_KEY --image 'frame.jpg' --prompt-file 'work\edit-prompt.txt' --out 'outputs\frame-edited.png'
```

Replace the example URL with an OpenAI Images API-compatible provider. Install the SDK if needed with `python -m pip install openai`; optional downscaling needs `pillow`.

## Named profiles

Copy `profiles.example.json` to `profiles.json` beside `SKILL.md`, then change URLs and environment variable names. Never put literal keys in JSON. A profile accepts `base_url`, `api_key_env` OR `api_key_file`, `model`, and `timeout` in seconds. Relative profile key-file paths resolve against the config directory; explicit `--api-key-file` paths resolve against the working directory.

```powershell
python $imageCli generate --profile custom --prompt-file 'work\prompt.txt' --out 'outputs\result.png'
python $imageCli generate --config 'C:\MyConfig\image-profiles.json' --profile studio --prompt 'A blue cat' --out 'outputs\cat.png'
python $imageCli generate --profile custom --base-url 'https://another-provider.example/v1' --api-key-env ANOTHER_IMAGE_KEY --prompt 'A blue cat' --out 'outputs\cat.png' --dry-run
```

An explicit URL overrides the profile URL; an explicit key selector overrides the profile key selector. URL and key selection are independent: when changing URL, select the corresponding key source as well.

Without a profile, URL uses `IMAGEGEN_BASE_URL`, then `OPENAI_BASE_URL`, then `https://api.openai.com/v1`. The key variable name is `IMAGEGEN_API_KEY_ENV` if set, otherwise `OPENAI_API_KEY`. An unset selected variable causes failure rather than substitution. Without an explicit/profile model, the official default is `gpt-image-2`.

## Local key file

Alternatively, create a local UTF-8 file containing only the key, outside shared workspaces and version control, then pass its path:

```powershell
python $imageCli generate --base-url 'https://your-provider.example/v1' --api-key-file 'C:\Private\image-api-key.txt' --prompt 'A blue cat' --out 'outputs\cat.png'
```

## Batch

Use JSONL with one object per line, e.g. `{"prompt":"A blue cat","out":"cat.png"}`. Provider and credentials apply to the whole invocation; split different providers into separate runs.

```powershell
python $imageCli generate-batch --profile custom --input 'work\jobs.jsonl' --out-dir 'outputs\batch' --concurrency 2 --max-attempts 3
```

Dry-run validates local arguments and payloads without network requests. Live compatibility requires accepting GPT Image models and the selected parameters, multipart edits, and returning `b64_json`, a `data:image/...` URI, or an HTTP(S) image URL. HTTP(S) image URLs are downloaded by the wrapper before saving. Other protocols need a separate adapter.
