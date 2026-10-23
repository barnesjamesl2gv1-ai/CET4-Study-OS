# 备份与 Windows 打包决策（2026-10-24）

- 问题：SQLite WAL 在线一致性备份、含原始文件的安全恢复，以及无需用户安装 Python/Node 的 Windows 安装包。
- 搜索：仓库 Skill 脚本查询 `sqlite online backup python restore` 与 `windows installer inno setup python pyinstaller`。搜索结果主要是小型第三方示例，许可证和维护状态不足以直接复制。
- 备份采用 Python 标准库 `sqlite3.Connection.backup`、`zipfile` 和 SHA-256，未复制第三方源码。恢复前验证数据库完整性、版本、所有文件清单及哈希，并先生成恢复前备份。
- 打包使用已安装的 [PyInstaller](https://github.com/pyinstaller/pyinstaller) 6.22.0 官方工具；其 [许可文件](https://github.com/pyinstaller/pyinstaller/blob/develop/COPYING.txt) 包含 GPL 与 bootloader exception。只调用发行版，不复制工具源码。
- 安装程序使用 [Inno Setup](https://jrsoftware.org/isinfo.php) 6.7.3 官方发行版；本机 `license.txt` 允许用于应用分发，需保留其声明。仓库只保存 `.iss` 脚本。
- 回退：卸载程序默认不删除 `%LOCALAPPDATA%\CET4StudyOS` 用户数据；应用内导出备份可作为升级前恢复材料。当前未做目标 Windows 11 电脑的安装/卸载/重装验证。
