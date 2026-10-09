# Imagegen Custom API

基于官方 **imagegen** 技能的独立 Codex 技能，支持选择 API Key 来源、Base URL 和服务配置，通过兼容 OpenAI Images API 的服务生成或编辑图片。

原官方技能无需修改。这个版本使用 API/CLI 工作流，不依赖内置图像生成工具。

## 功能

- 文生图、图片编辑、PNG 遮罩参数、JSONL 批量生成。
- 通过命名 profile 切换 Base URL、模型和凭据来源。
- API Key 从环境变量或本地 UTF-8 文件读取，不作为命令行参数传入。
- 兼容 `b64_json`、图片 Data URI 和 HTTP(S) 图片 URL 返回；下载图片时不转发 API Key。
- 支持 dry-run 检查请求配置，避免测试配置时消耗生成额度。

## 安装

需要 Python 3.10+、可访问的兼容 Images API 服务及其 API Key。

将仓库克隆到 Codex 技能目录（Windows PowerShell）：

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex\skills\imagegen-custom-api'
git clone https://github.com/XC-star3/imagegen-custom-api.git $skillDir
python -m venv (Join-Path $skillDir '.venv')
& (Join-Path $skillDir '.venv\Scripts\python.exe') -m pip install -r (Join-Path $skillDir 'requirements.txt')
```

若设置了 `CODEX_HOME`，将技能安装到该目录的 `skills/imagegen-custom-api`。已有同名技能时，先备份本地修改，避免覆盖。安装后重新打开 Codex，并确认技能列表出现 `imagegen-custom-api`。

## 配置 API

在 Windows 的“环境变量 → 用户变量”中新增 `MY_IMAGE_API_KEY`，值为你的 API Key，然后完全退出并重启 Codex。不要将真实 Key 发到聊天或提交进仓库。

复制 `profiles.example.json` 为 `profiles.json`，修改 `custom` 配置：

```json
{
  "profiles": {
    "custom": {
      "base_url": "https://your-provider.example/v1",
      "api_key_env": "MY_IMAGE_API_KEY",
      "model": "gpt-image-2",
      "timeout": 180
    }
  }
}
```

示例域名需要替换。Base URL 是 API 根地址，通常以 `/v1` 结尾，而不是完整的 `/images/generations` 或 `/images/edits` 地址。模型必须受服务支持；默认模型不代表每个第三方服务都提供该模型。

在 Codex 中调用：

> 使用 $imagegen-custom-api 的 custom 配置，将上传截图中的人物替换为蓝色动漫人物，保留原构图和背景。

也可以直接指定服务：

> 使用 $imagegen-custom-api，Base URL 为 https://你的服务地址/v1，Key 从 MY_IMAGE_API_KEY 环境变量读取，编辑这张图片。

## CLI 用法

```powershell
$skillDir = Join-Path $env:USERPROFILE '.codex\skills\imagegen-custom-api'
$imagePython = Join-Path $skillDir '.venv\Scripts\python.exe'
$imageCli = Join-Path $skillDir 'scripts\image_gen.py'

# 只验证本地配置；不联网、不生成图片
& $imagePython $imageCli generate --profile custom --prompt 'Blue underwater anime illustration' --out 'outputs\test.png' --dry-run

# 生成图片
& $imagePython $imageCli generate --profile custom --prompt 'Blue underwater anime illustration' --out 'outputs\result.png'

# 编辑图片：长提示词推荐存为 UTF-8 文件
& $imagePython $imageCli edit --profile custom --image 'frame.jpg' --prompt-file 'prompt.txt' --no-augment --out 'outputs\frame-edited.png'

# 单次指定服务及凭据变量
& $imagePython $imageCli generate --base-url 'https://your-provider.example/v1' --api-key-env MY_IMAGE_API_KEY --prompt 'A blue cat' --out 'outputs\cat.png'

# 指定本地 Key 文件
& $imagePython $imageCli generate --base-url 'https://your-provider.example/v1' --api-key-file 'C:\Private\image-api-key.txt' --prompt 'A blue cat' --out 'outputs\cat.png'
```

Linux/macOS 可使用 `python3` 和相应虚拟环境路径运行同一脚本。可通过 `generate --help` 查看参数。

批量任务 JSONL，每行一个对象：

```jsonl
{"prompt":"A blue cat","out":"cat.png"}
{"prompt":"An underwater landscape","out":"water.png"}
```

```powershell
& $imagePython $imageCli generate-batch --profile custom --input 'jobs.jsonl' --out-dir 'outputs\batch' --concurrency 2 --max-attempts 3
```

## 配置优先级

| 项目 | 优先级（从高到低） |
| --- | --- |
| Base URL | `--base-url` → profile → `IMAGEGEN_BASE_URL` → `OPENAI_BASE_URL` → 官方地址 |
| Key 来源 | `--api-key-env` / `--api-key-file` → profile → `IMAGEGEN_API_KEY_ENV` 指定的变量 → `OPENAI_API_KEY` |
| 模型 | `--model` → profile → 官方脚本默认值 |
| 超时 | `--timeout` → profile → 180 秒 |

配置也可通过 `--config` 指定。选定凭据源为空时会报错，不会自动使用另一个账户的 Key。修改服务地址时，应同时选择对应的凭据源。

## 兼容性与已知限制

- 适用于 OpenAI-compatible Images API，不是任意图像平台的通用适配器。
- 保留官方 `gpt-image-*` 模型和图像参数校验。自定义模型别名可能需要扩展。
- 支持同步生成/编辑响应。异步任务 ID、轮询接口和其他响应协议未适配。
- 第三方服务可能忽略尺寸、长宽比、遮罩或提示词约束。实际测试中遇到过 `auto` 返回正方形、遮罩区域输出黑块、人物姿势/服饰变化等问题；遮罩参数不保证像素级保留。
- `gpt-image-2` 的官方 CLI 校验不支持透明背景。其他模型和服务的能力需另行确认。
- `--dry-run` 不验证网络、鉴权和模型实际可用性。模型列表查询成功也不证明图像编辑完全兼容。
- 生成调用可能计费；超时不代表服务端任务取消，不应仅因本地没有文件就重复付费请求。
- 图片 URL 由服务返回；工具需要网络访问来下载结果。

## 测试

```powershell
python test_image_skill.py
```

离线测试使用模拟 SDK 和虚构凭据，不进行真实 API 请求，覆盖配置优先级、凭据来源、生成、编辑、批量、dry-run、错误脱敏和响应格式。第三方服务的输出质量和遮罩支持需要单独验证。

## 来源与许可证

派生自 OpenAI 官方 imagegen 技能（[openai/skills](https://github.com/openai/skills)）。`scripts/image_gen_core.py` 是创建本技能时捆绑的官方 CLI 副本；保留原始 Apache-2.0 许可证，见 [LICENSE.txt](LICENSE.txt)。本项目与官方 imagegen 独立维护。

修改部分包括：新增可配置 API 包装脚本、命名配置、凭据来源选择、响应格式转换、脱敏处理、技能入口、使用说明和离线测试。提示词参考及 CLI 参考来自官方技能，部分入口说明已调整。
