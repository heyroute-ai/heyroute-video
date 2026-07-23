# Manifest v1

Manifest 是 Agent 提交给 heyroute-video 的唯一任务描述。`.json` 和 `.yaml`/`.yml` 使用同一套字段，读取后转换成内部模型。

## 顶层字段

| 字段 | 必填 | 说明 |
|---|---:|---|
| `version` | 否 | 当前只能是 `1`，默认值为 `1` |
| `job_id` | 是 | 任务唯一标识；批量模式下每个 job 都要有自己的值 |
| `profile` | 否 | 输出 profile，默认 `vertical-news-1080x1920` |
| `output` | 否 | 输出目录和画面规格 |
| `voice` | 否 | TTS provider、参考音频和参数 |
| `scenes` | 是 | 按顺序排列的画面场景 |
| `publish` | 否 | 标题、简介和标签 |

## Scene

每个场景必须有唯一 `id` 和 `visual`。有旁白时使用 `voiceover.text`；没有旁白时必须填写 `duration`，系统会插入等长静音。

Phase 1 支持：

```yaml
visual:
  type: image
  path: ./assets/news.png
```

以及用于离线测试的纯色画面：

```yaml
visual:
  type: color
  color: "#173f46"
```

`layout` 记录模板意图（例如 `cover`、`evidence`、`visual`、`editorial`），当前渲染器保持静态画面，不会静默替换素材或猜测版式。

## Voice

```yaml
voice:
  provider: fake       # 测试；生产使用 indextts
  reference_audio: ./assets/voice.wav
  language: zh-CN
  options:
    project_path: E:/index-tts
    fp16: true
```

`indextts` provider 会通过独立的 IndexTTS integration 生成分段 WAV，并用文本、参考音频哈希和参数生成缓存键。云端 provider 不在 Phase 1 范围内。

## 批量模式

一个文件可以用 `jobs` 代替顶层 `job_id` 与 `scenes`，顶层的 `version`、`profile`、`voice` 等字段会被每个 job 继承。没有显式 `output.directory` 时，系统使用 `./output/<job_id>`，避免批量任务互相覆盖。
