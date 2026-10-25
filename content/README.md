把需要阅读的 Markdown 文件放进这个目录，然后运行：

    python build.py

生成结果：index.generated.html（模板和原文都不会被修改）

常用参数：

    python build.py --split                按标题把单个文件拆成多章
    python build.py --content 我的文档.md    指定单个文件
    python build.py --title "书名" --description "简介"
    python build.py --force                覆盖已有的生成文件
