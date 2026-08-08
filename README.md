# VS Code Dark Modern Enhanced

一个面向 Sublime Text 4 的代码配色包：从 VS Code 的 `dark_vs.json`、`dark_plus.json` 和 `dark_modern.json` 构建，尽量在 Sublime 的 TextMate scopes 与可选 LSP 语义 token 上重现 VS Code Dark Modern 的代码高亮。

它不是语言解析器，也不会在每次输入时扫描文件或用 `add_regions()` 重绘代码。基础高亮完全由 Sublime color scheme 完成，因此性能与内置主题处于同一量级。

## 安装与使用

### Package Control

在包进入 Package Control 默认频道前，可以直接添加 GitHub 仓库：

1. 打开 Command Palette，运行 `Package Control: Add Repository`。
2. 输入 `https://github.com/xiaolingxiaoying/VSCodeDarkModernEnhanced`（末尾不要加 `.git`）。
3. 再运行 `Package Control: Install Package`，搜索并安装 **VS Code Dark Modern Enhanced**。

包被默认频道收录后可以省略前两步，直接搜索安装。安装完成后，运行下面任一命令启用配色：

- `VS Code Dark Modern: Select Enhanced Color Scheme`
- `Preferences: Select Color Scheme`，然后选择 **VS Code Dark Modern Enhanced**

### 从源码安装

将仓库克隆到 Sublime Text 的 `Packages` 目录：

```powershell
git clone https://github.com/xiaolingxiaoying/VSCodeDarkModernEnhanced.git `
  "$env:APPDATA\Sublime Text\Packages\VS Code Dark Modern Enhanced"
```

仓库已经包含生成后的 color scheme，安装使用无需运行 Python。只有修改源主题或映射时才需要重新构建：

```powershell
python tools/build_theme.py
```

构建会输出：

- `VS Code Dark Modern Enhanced.sublime-color-scheme`：Sublime 实际加载的配色文件。
- `theme-build-report.json`：规则、颜色来源和未映射 VS Code UI 颜色的报告。

只校验输入和映射而不写文件：

```powershell
python tools/build_theme.py --check
```

构建器只使用 Python 标准库，支持 VS Code JSONC 注释、尾随逗号和递归 `include`。它按 `dark_vs.json → dark_plus.json → dark_modern.json` 解析：父主题 token 规则优先输出，子主题规则后输出；`colors` 与 `semanticTokenColors` 由子主题覆盖。

### 与旧版主题共存

本包使用独立名称，不会覆盖 `Packages/User/VS Code Dark Modern.sublime-color-scheme`。旧配色可以继续保留、切换和对照。

`.sublime-theme` 控制 Sublime 界面，`.sublime-color-scheme` 控制编辑区代码颜色，两者可以混合使用。如果已经有 `VS Code Dark Modern.sublime-theme`，可以在 Preferences 设置中保留旧 UI 主题，同时启用增强配色：

```json
{
    "theme": "VS Code Dark Modern.sublime-theme",
    "color_scheme": "VS Code Dark Modern Enhanced.sublime-color-scheme"
}
```

## LSP 语义高亮（可选）

安装 [LSP](https://packagecontrol.io/packages/LSP) 以及所用语言的服务器插件，并在 LSP 设置中启用：

```json
{
    "semantic_highlighting": true
}
```

没有 LSP 时，主题仍可使用 Sublime 的原生 syntax scopes 完成基础高亮。LSP 可进一步将函数、方法、参数、属性、类型、枚举成员和只读值区分开来。语言服务器是否支持 semantic tokens、启动时间和大工程的资源消耗由该服务器决定；本包不会安装、启动或修改任何 LSP 配置。

## 语言与文档格式

主题不按文件扩展名限制语言：任何已安装的 Sublime syntax 都会使用通用 TextMate scope 规则。第一版针对 Sublime 常见 scopes 调校了 JavaScript、TypeScript/TSX、Python、C/C++、C#、Java、Go、Rust、HTML、CSS、JSON 和 YAML；TypeScript/TSX 需要本机存在对应 syntax。

Markdown 覆盖标题、强调、删除线、列表、引用、链接、URL、行内代码、围栏、表格和嵌入 HTML。常见扩展名包括 `.md`、`.mdown`、`.mdwn`、`.markdown` 和 `.markdn`；围栏中的代码使用已安装语言 syntax 的规则。

LaTeX/TeX 覆盖命令、宏、环境、章节、参数、引用、citation、数学运算符、数字、分组符号和注释；内置 LaTeX syntax 通常关联 `.tex` 与 `.ltx`。

视觉结果会接近 VS Code，但不保证逐字符一致：Sublime syntax、第三方语法包和各语言服务器产出的 scopes/tokens 可能与 VS Code 的 grammar 不同。

## 命令

- `VS Code Dark Modern: Select Enhanced Color Scheme`
- `VS Code Dark Modern: Inspect Highlight`：显示光标下文本的 Sublime scopes、可用的语义 token、命中规则与颜色来源。
- `VS Code Dark Modern: Check Semantic Highlighting`：检查 LSP 语义高亮的可用状态并给出配置提示。

## 性能与边界

基础方案是静态 `.sublime-color-scheme`，打开、滚动和编辑不会触发本包的全缓冲区扫描。超大文件的语法高亮策略由 Sublime 管理；若启用了 LSP，额外 CPU、内存和索引时间来自语言服务器。为避免输入延迟，本包不实现 `on_modified` 分析器，也不以 regions 覆盖常规前景色。

此包只提供编辑区和代码高亮，不尝试复刻 VS Code 的 Activity Bar、Chat、侧栏、标签栏等 UI。构建报告会列出这些无法映射到 Sublime color scheme 的 UI 色。

## 颜色来源与许可证

配色源文件来自 [microsoft/vscode](https://github.com/microsoft/vscode) 的 Dark Modern / Dark+ / Dark (Visual Studio) 主题链，并受其 [MIT License](https://github.com/microsoft/vscode/blob/main/LICENSE.txt) 约束。本仓库的适配代码和文档同样以 MIT License 发布；详见 [LICENSE](LICENSE)。

发布到 Package Control 时不要提交 `package-metadata.json`；该文件由 Package Control 在安装阶段自动生成。仓库应通过语义化 Git tag 发布，并在 Package Control 默认 channel 中声明 `sublime_text: ">=4095"`。

本项目与 Microsoft 或 Visual Studio Code 无关联，也未获其背书。
