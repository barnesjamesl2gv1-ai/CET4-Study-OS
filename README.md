# CET-4 Study OS

面向个人 Windows 11 + Edge 的本地英语四级备考平台。当前为 **0.1.0 MVP 预览版**；已实现本地导入、人工核对、自由训练及备份恢复，但尚未完成真实材料和目标机实机验收。

## Windows 安装

在本机执行 `powershell -ExecutionPolicy Bypass -File scripts/build_windows.ps1` 可运行测试并生成 `artifacts/CET4-Study-OS-0.1.0-Setup.exe`。安装后双击桌面快捷方式，在 Microsoft Edge 使用本地页面。安装包生成不等于目标机验收；按 [验收指南](docs/ACCEPTANCE_GUIDE.md)完成真实材料测试。

可在页面创建试卷，分别上传试卷、答案和 MP3，逐题人工核对后练习。听力须预览并确认片段。日常训练可随时看答案，不计分；“备份与恢复”提供每日备份、手动备份、导出和恢复。

## 开发运行

安装 Python 依赖：`python -m pip install -r backend/requirements.txt`。在 `frontend/` 运行 `npm ci` 与 `npm run build`。随后在仓库根目录运行 `python -m launcher.windows_launcher`，启动器只监听 `127.0.0.1`，会打开 Microsoft Edge；再次启动时会复用现有服务，默认端口占用时会选择空闲端口。

数据默认保存在 `%LOCALAPPDATA%\CET4StudyOS`；开发测试可设置 `CET4_DATA_DIR` 指向独立临时目录。

## 当前可运行内容

`python -m backend.m0_inspect <文件或目录> --output reports/m0.json` 检查输入文件类型、大小、SHA-256 和基础可读性，生成 JSON 报告。PDF 文本提取依赖 pypdf，图片 OCR 依赖 Tesseract 和 pytesseract，音频时长检查依赖 ffprobe。缺少工具时报告明确标记为待验证，不会判定材料可用于正式模考。

安装可选依赖：`python -m pip install -r backend/requirements-m0.txt`。运行测试：`python -m pytest -q`。

报告包含源文件绝对路径，属于本机诊断数据，请勿上传到公开仓库。真实试卷、音频、学习记录和备份也不要提交到 Git。

## 下一步

使用至少一套本人有权使用的 PDF、DOCX、扫描图片及 MP3 混合材料，在目标 Windows 11 + Edge 机器按 `docs/ACCEPTANCE_GUIDE.md` 做完整验收。需求和原始验收标准见 `docs/spec/`；阶段进展见 `docs/IMPLEMENTATION_STATUS.md`。
