# PDF 提取依赖决策（2026-10-24）

- 问题：本地离线读取可提取文本的 PDF；扫描件必须报告待人工核对。
- 搜索：仓库 Skill 脚本查询 `python pdf text extraction offline`、`pdf text extraction pypdf`，并检查上游仓库的 LICENSE。第一次搜索 API 成功，但 Windows GBK 控制台输出个别字符失败；设置 UTF-8 后第二次成功。

| 候选 | 许可核验 | 决定 |
|---|---|---|
| [pypdf](https://github.com/py-pdf/pypdf) | 仓库 [LICENSE](https://github.com/py-pdf/pypdf/blob/main/LICENSE) 列有 BSD 风格再分发条件；安装发行包 6.21.2 | 使用官方包的 `PdfReader`，不复制源代码 |
| [python-docx](https://github.com/python-openxml/python-docx) | 仓库 [LICENSE](https://github.com/python-openxml/python-docx/blob/master/LICENSE) 标记 MIT | 当前 DOCX 只读取 ZIP 中的 XML，不新增运行时依赖 |
| [PyMuPDF](https://github.com/pymupdf/PyMuPDF) | 仓库 [COPYING](https://github.com/pymupdf/PyMuPDF/blob/main/COPYING) 为 AGPLv3 | 本阶段不采用，避免公开分发时产生未经审查的许可义务 |

仅传入本机文件，不发送用户资料到 GitHub。pypdf 对扫描页无法自动识别文字，解析异常标记为无效；基础解析通过也须人工核对题目与答案。依赖版本锁在 `backend/requirements.txt`。回退方式：还原本次依赖与解析器提交；原始上传文件和数据库不得删除。
