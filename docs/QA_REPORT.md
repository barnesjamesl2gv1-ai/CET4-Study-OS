# MVP 自动化验证与未完成验收

截至 2026-10-24，M0 到 M1-D 已完成代码阶段提交。自动化测试仅使用自编样例，不代表真实四级资料验收。

| 验证项 | 结果 |
|---|---|
| `python -m pytest -q` | 19 项自动化测试通过（提交前以最终运行结果为准） |
| `npm run build --prefix frontend` | React 生产构建通过 |
| `npm audit --audit-level=moderate` | 0 项已报告漏洞 |
| PyInstaller 程序 `--self-test` | 通过；验证可导入后端与初始化临时 SQLite |
| Inno Setup 编译 | 已生成 `CET4-Study-OS-0.1.0-Setup.exe`，构建日志可复现 |
| Windows 11 + Edge 安装/操作/卸载重装 | 未执行目标机实测 |
| 用户真实 PDF/DOCX/图片/MP3 与答案对齐 | 未提供材料，未执行 |
| 真实音频切分质量 | 未提供材料，未执行 |

已知限制：扫描 OCR 依赖另行安装 Tesseract；FFmpeg 不随安装包分发，缺失时仍可手工确认片段；作文、翻译仅展示题目，不在 MVP 中评分；本阶段不开发正式模考与成绩趋势。自动化测试中的合成 MP3 是 2 秒正弦波。

安装包在本地 `artifacts/`，不会作为 Git 源代码提交。发布前请核对其 SHA-256 和预览版说明。完整实机验收步骤见 `docs/ACCEPTANCE_GUIDE.md`。

本次安装包 SHA-256：`FCE122CF8B9886D11C8B638D69D010F2C700FF9CE89CA75A960F79A86E53CB6E`（本地文件大小 35,276,741 字节）。
