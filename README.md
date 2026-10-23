# CET-4 Study OS

面向个人 Windows 11 + Edge 的本地英语四级备考平台。当前仓库正在开发 MVP；尚未完成真实材料或安装包实机验收。

## 开发运行

安装 Python 依赖：`python -m pip install -r backend/requirements.txt`。在 `frontend/` 运行 `npm ci` 与 `npm run build`。随后在仓库根目录运行 `python -m launcher.windows_launcher`，启动器只监听 `127.0.0.1`，会打开 Microsoft Edge；再次启动时会复用现有服务，默认端口占用时会选择空闲端口。

数据默认保存在 `%LOCALAPPDATA%\CET4StudyOS`；开发测试可设置 `CET4_DATA_DIR` 指向独立临时目录。

## 当前可运行内容

`python -m backend.m0_inspect <文件或目录> --output reports/m0.json` 检查输入文件类型、大小、SHA-256 和基础可读性，生成 JSON 报告。PDF 文本提取依赖 PyMuPDF，图片 OCR 依赖 Tesseract 和 pytesseract，音频时长检查依赖 ffprobe。缺少工具时报告明确标记为待验证，不会判定材料可用于正式模考。

安装可选依赖：`python -m pip install -r backend/requirements-m0.txt`。运行测试：`python -m pytest -q`。

报告包含源文件绝对路径，属于本机诊断数据，请勿上传到公开仓库。真实试卷、音频、学习记录和备份也不要提交到 Git。

## 下一步

使用至少一套本人有权使用的 PDF、DOCX、扫描图片及 MP3 混合材料在目标 Windows 11 机器运行 M0 检查，人工核对提取文本、答案对齐与音频切分效果。通过后再开展 M1 本地服务、练习与备份等开发。需求和验收标准见 `docs/spec/`。
