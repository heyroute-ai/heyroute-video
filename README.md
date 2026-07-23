# heyroute-video

配置驱动的开源批量视频生产流水线。

`heyroute-video` 面向需要稳定、可复现地批量制作视频的人和团队，提供从结构化内容、图片/PPT 素材、配音，到字幕、渲染和发布包的实用工具。它不绑定某个内容领域、模型供应商或发布平台。

## 目标

- 把“一个视频怎么做”变成可复用的配置和流水线
- 支持竖屏视频、旁白、字幕、图片与幻灯片素材
- 对单条任务和批量任务使用同一套输入格式
- 每一步都有可检查的中间产物、日志和失败原因
- 将发布平台做成可选适配器，不要求用户交出账号凭据

首个参考实现来自个人项目 [ahe-ai-video-workflow](https://github.com/heyroute-ai/heyroute-video)，但本仓库会重新整理为可分享、可测试、可扩展的公共工具，而不是直接复制旧项目的目录和个人配置。

## 计划中的流水线

```text
内容清单 / manifest
        ↓
素材校验与标准化
        ↓
场景时间线（图片、PPT 页、文字、音频）
        ↓
本地配音适配器（IndexTTS）
        ↓
字幕生成与校对
        ↓
FFmpeg 渲染 + 质量检查
        ↓
视频、封面、字幕、说明和发布清单
```

核心库只负责内容到视频的生产；账号登录、上传和平台规则放在独立的 `publishers/` 适配器中，默认关闭。

## 预计目录

```text
heyroute-video/
├─ src/heyroute_video/       # 可复用核心库与 CLI
│  ├─ manifest/              # 输入规范与加载
│  ├─ media/                 # 图片、PPT、音频标准化
│  ├─ timeline/              # 场景与时间线模型
│  ├─ tts/                   # TTS provider 接口
│  ├─ subtitles/             # 字幕生成、切分、校验
│  ├─ render/                # FFmpeg 渲染器
│  └─ validate/              # 尺寸、时长、音画和文件检查
├─ templates/                # 可复用视频版式与示例配置
├─ examples/                 # 不含私有素材和凭据的完整例子
├─ publishers/               # 可选的平台发布适配器
├─ tests/
├─ docs/
└─ PLAN.md
```

## 当前状态

仓库目前已具备 Phase 0/1 的可运行骨架：manifest 校验、JSON 事件、fake TTS、IndexTTS 适配、SRT/VTT 和 FFmpeg 9:16 渲染。第一阶段优先跑通“一份 manifest → 一条 9:16 旁白视频 + SRT + 发布包”，再扩展到模板和平台适配器。

## 快速开始

安装开发依赖：

```powershell
uv sync --extra dev
```

先用完全离线的 fake provider 验证整条流水线：

```powershell
uv run heyroute-video doctor --json
uv run heyroute-video validate --manifest examples/news.yaml --json
uv run heyroute-video build --manifest examples/news.yaml --json-events
```

产物默认位于 `examples/output/example-news/`。使用本地 IndexTTS 时，将 manifest 中的 `voice.provider` 改为 `indextts`，填写 `reference_audio`，然后先运行：

```powershell
uv run heyroute-video tts doctor --json
```

Agent 集成时使用 `--json` 获取最终对象，使用 `--json-events` 获取逐行进度。缺素材、FFmpeg 不可用或 IndexTTS 失败都会返回非零退出码和稳定错误码。发布包包含 `video.mp4`、`cover.png`、`audio.wav`、`subtitle.srt`、`subtitle.vtt`、`title.txt`、`description.txt`、`tags.txt`、`manifest.resolved.json` 和 `build-report.json`。

## 许可证

本项目采用 [PolyForm Noncommercial 1.0.0](LICENSE)。允许个人、研究、教育和其他非商业用途；禁止商业使用。该许可证允许公开查看和修改源码，但不属于 OSI 认可的标准 Open Source license。商业合作或商业授权请联系项目维护者。

## 参与贡献

欢迎提交 Issue、改进文档和不含私有凭据的通用工具。贡献前请先阅读 `PLAN.md`，涉及新平台、新模型或新许可证的改动请先开 Issue 讨论。
