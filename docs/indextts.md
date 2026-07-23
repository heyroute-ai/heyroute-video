# IndexTTS 集成边界

heyroute-video 使用本地 IndexTTS，不接入云端语音服务。适配层位于本项目，IndexTTS 源码、模型权重和运行环境保持在独立目录。

## 当前本机运行时

开发机当前可使用：

```text
E:\index-tts
E:\index-tts\.venv\Scripts\python.exe
E:\index-tts\integration\generate_from_job.py
E:\index-tts\checkpoints
```

也可以通过 `HEYROUTE_INDEXTTS_HOME` 或 manifest 中的 `voice.options.project_path` 指定其他目录。

## 命令

```powershell
heyroute-video tts doctor --json
heyroute-video tts bootstrap --json
```

`bootstrap` 只负责检查并给出准备提示，不会自动下载模型或覆盖用户现有 IndexTTS 环境。模型体积大、上游许可独立，下载和升级必须由使用者明确执行。

## 许可与责任

IndexTTS 使用其上游提供的模型使用协议和免责声明。heyroute-video 不重新分发 IndexTTS 源码、模型或参考音频，只调用用户本机已准备好的运行时。使用者必须同时遵守：

1. heyroute-video 的 PolyForm Noncommercial 1.0.0；
2. IndexTTS 上游的模型使用协议、免责声明和第三方依赖许可；
3. 参考音频、合成声音和视频内容所在地的法律及平台规则。

不要将 `E:\index-tts`、模型权重、`.venv`、参考音频或包含本机路径的 job 文件提交到本仓库。
