# -*- coding: utf-8 -*-

# -------------------------------------------------------------------------------
# Name:         demo
# Description:
# Author:       shaver
# Date:         2025/8/28
# -------------------------------------------------------------------------------
from ebooklib import epub
import re


def txt_to_epub(txt_file_path, epub_file_path, book_title="转换的电子书", author="未知作者"):
    """
    将TXT文件转换为EPUB格式的电子书

    参数:
    txt_file_path (str): 输入的TXT文件路径
    epub_file_path (str): 输出的EPUB文件路径
    book_title (str): 电子书标题，默认为"转换的电子书"
    author (str): 作者名，默认为"未知作者"
    """

    # 创建EPUB书籍对象
    book = epub.EpubBook()

    # 设置书籍的唯一标识符（使用标题和当前时间戳生成一个简单的标识）
    import time
    book_id = f"book_{int(time.time())}"
    book.set_identifier(book_id)

    # 设置书籍元数据
    book.set_title(book_title)
    book.set_language('zh-CN')  # 中文
    book.add_author(author)

    # 读取TXT文件内容
    try:
        with open(txt_file_path, 'r', encoding='utf-8') as file:
            content = file.read()
    except UnicodeDecodeError:
        # 如果UTF-8解码失败，尝试其他常见编码
        try:
            with open(txt_file_path, 'r', encoding='gbk') as file:
                content = file.read()
        except Exception as e:
            print(f"无法读取文件: {e}")
            return False

    # 预处理内容：按行分割并移除空行
    lines = [line.strip() for line in content.split('\n') if line.strip()]

    # 智能章节检测（尝试识别常见的章节标题模式）
    chapters = []
    current_chapter = []
    chapter_count = 0

    for line in lines:
        # 检测章节标题（例如：第一章、Chapter 1、第1章等）
        if (re.match(r'^(第[零一二三四五六七八九十百千万\d]+章)', line) or
                re.match(r'^(章节\d+)', line) or
                re.match(r'^(CHAPTER|Chapter)\s+\d+', line, re.IGNORECASE) or
                re.match(r'^[§\*]', line) or
                len(line) < 50 and not any(char.islower() for char in line)):

            # 如果当前章节有内容，保存前一章节
            if current_chapter:
                chapter_content = '\n'.join(current_chapter)
                chapters.append({
                    'title': f"第{chapter_count}章",
                    'content': chapter_content
                })
                current_chapter = []
                chapter_count += 1

            # 新章节标题
            current_chapter.append(f"<h1>{line}</h1>")
        else:
            # 普通段落
            current_chapter.append(f"<p>{line}</p>")

    # 添加最后一个章节
    if current_chapter:
        chapter_content = '\n'.join(current_chapter)
        chapters.append({
            'title': f"第{chapter_count}章" if chapter_count > 0 else "正文",
            'content': chapter_content
        })

    # 如果没有检测到章节，将整个内容作为一个章节
    if not chapters:
        full_content = '\n'.join([f"<p>{line}</p>" for line in lines])
        chapters.append({
            'title': "正文",
            'content': full_content
        })

    # 创建章节对象并添加到书籍
    spine = ['nav']
    toc = []

    for i, chapter_info in enumerate(chapters, 1):
        chapter = epub.EpubHtml(
            title=chapter_info['title'],
            file_name=f'chap_{i}.xhtml',
            lang='zh-CN'
        )
        chapter.content = f"""
        <!DOCTYPE html>
        <html xmlns="http://www.w3.org/1999/xhtml">
        <head>
            <meta charset="utf-8" />
            <title>{chapter_info['title']}</title>
        </head>
        <body>
            {chapter_info['content']}
        </body>
        </html>
        """

        book.add_item(chapter)
        spine.append(chapter)
        toc.append(epub.Link(f'chap_{i}.xhtml', chapter_info['title'], f'chap_{i}'))

    # 设置目录
    book.toc = tuple(toc)

    # 添加导航文档
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())

    # 设置书籍阅读顺序
    book.spine = spine

    # 写入EPUB文件
    try:
        epub.write_epub(epub_file_path, book, {})
        print(f"转换成功！EPUB文件已保存至: {epub_file_path}")
        return True
    except Exception as e:
        print(f"转换失败: {e}")
        return False


# 使用示例
if __name__ == "__main__":
    # 基本用法
    txt_to_epub(
        txt_file_path="input.txt",  # 输入的TXT文件路径
        epub_file_path="output.epub",  # 输出的EPUB文件路径
        book_title="我的电子书",  # 电子书标题
        author="作者姓名"  # 作者名
    )

    # 或者使用默认参数
    # txt_to_epub("input.txt", "output.epub")

