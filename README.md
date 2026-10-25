# md2html

把 Markdown 文档转换成单文件、可离线阅读的 HTML 阅读器。

演示网站：[演示Demo](https://md2html.banqiuxy.top)

## 目录结构

```text
md2html/
├── index_template.html   页面模板，含 {{...}} 占位符，不要手改数据块
├── build.py              构建脚本
├── book.json             书名、简介等书籍信息
├── content/              放你的 Markdown 文件
└── index.generated.html  生成结果（可随时删除重建）
```

## 使用

1. 把 `.md` 文件放进 `content/`。
2. 在 `book.json` 填写书名和简介，或用命令行参数覆盖。
3. 运行：

```bash
python build.py
```

4. 打开 `index.generated.html`。

模板和 Markdown 原文都不会被修改。`index.generated.html` 已存在时会停止，确认后加 `--force` 覆盖。

## 命令行参数

| 参数 | 说明 |
| --- | --- |
| `--content` | 指定 Markdown 文件或目录，默认 `content/` |
| `--template` | 指定模板，默认 `index_template.html` |
| `--output` | 指定输出，默认 `index.generated.html` |
| `--config` | 指定书籍信息 JSON，默认 `book.json` |
| `--title` | 覆盖书名 |
| `--description` | 覆盖简介 |
| `--eyebrow` | 覆盖侧栏顶部小字 |
| `--split` | 按每个文件的一级/二级标题拆分成多章 |
| `--force` | 允许覆盖已有输出文件 |

## 章节划分

- 默认：目录里每个 `.md` 文件算一章，按文件名排序。
- 加 `--split`：单个文件按 `#` / `##` 标题拆成多章，适合把一本长文做成多章。
- 章节标题优先取文件里的第一个标题，否则用文件名。

## 支持的 Markdown

标题、段落、**加粗**、*斜体*、`行内代码`、代码块、引用、无序/有序列表、表格、图片、链接、分隔线。

HTML 会被转义，页面不会执行 Markdown 里内嵌的脚本。

## 阅读器功能

左侧目录、全文搜索与关键词高亮、阅读进度、上下章导航、字号与行距调整、日间/夜间模式、自动保存阅读位置。也支持在页面上临时导入其他 Markdown 文件。

## 注意

图片使用相对路径时，生成的 HTML 需要和图片放在同一目录才能显示；用绝对地址则不受影响。
