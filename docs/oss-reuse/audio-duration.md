# 音频时长依赖决策（2026-10-24）

- 问题：本地确认 MP3 可读取且片段边界不越界；静音检测只提供待人工确认的候选。
- 搜索：仓库 Skill 脚本查询 `mp3 duration metadata python tinytag`、`ffmpeg silence detection audio segmentation`。前者无返回候选，随后直接核对 TinyTag 官方仓库；后者候选质量与许可均未经验证。
- [TinyTag](https://github.com/tinytag/tinytag) 2.3.2：官方 [LICENSE](https://github.com/tinytag/tinytag/blob/master/LICENSE) 为 MIT，采用发行包 API 获取时长，不复制源码。分发时保留其版权及许可声明。
- [FFmpeg](https://github.com/FFmpeg/FFmpeg)：只在本机发现已有 `ffmpeg` 时调用 `silencedetect` 生成候选；没有可执行文件时仍可人工按完整 MP3 时长确认片段。当前仓库不捆绑 FFmpeg，Windows 安装包若日后捆绑须核对具体构建的 LGPL/GPL 选项和许可证。
- 音频始终在本机处理，不发送到 GitHub。候选不会自动成为已确认片段；自动化测试使用自编 2 秒正弦波，不代表真实四级音频切分验收。
- 回退：移除 TinyTag API 后停止新 MP3 上传，保留已有原文件和数据库记录，不删除用户资料。
