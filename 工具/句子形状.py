#!/usr/bin/env python3
"""只读统计句子形状，不判断文笔、作者身份或是否需要改稿。

用法：python3 -I 工具/句子形状.py <文章.md>... [--reference <参考稿.md>] [--json]
--reference 可以重复，只展示明确选中的稿件，不自动挑选或合并成达标线。
标题、图片、表格、引用、围栏和缩进代码不计入正文。正文按空行分段，
段内按中文句号、中英文问号和感叹号断句；短句和段末未加句号的文字也计数。
长度是不含空白与断句标点的字符数，逗号数只统计中文逗号。
"""

import argparse
import json
import re
from pathlib import Path


NOTE = '只展示描述统计；参考稿由你指定，数字不是写作目标，也不用于判断是否像 AI。'
FENCE = re.compile(r'^ {0,3}(`{3,}|~{3,})(.*)$')
TABLE_RULE = re.compile(r'^\s*\|?\s*:?-{3,}:?\s*(?:\|\s*:?-{3,}:?\s*)+\|?\s*$')


def plain_inline(text):
    # 保留链接文字；图片、行内代码和格式标记不参与句长统计。
    text = re.sub(r'!\[[^\]]*\](?:\([^\n]*?\)|\[[^\]]*\])', '', text)
    text = re.sub(r'`+[^`]*`+', '', text)
    text = re.sub(r'\[([^\]]+)\](?:\([^\n]*?\)|\[[^\]]*\])', r'\1', text)
    return re.sub(r'[*_~]', '', text)


def prose_paragraphs(text):
    """识别本工作台常用的 Markdown 块，不把不同段落接成长句。"""
    lines = text.splitlines()
    paragraphs, current = [], []
    fence = None
    in_table = in_quote = False

    def flush():
        paragraph = plain_inline('\n'.join(current)).strip()
        if paragraph and any(char.isalnum() for char in paragraph):
            paragraphs.append(paragraph)
        current.clear()

    for index, line in enumerate(lines):
        stripped = line.strip()
        marker = FENCE.match(line)
        if fence:
            if marker and marker[1][0] == fence[0] and len(marker[1]) >= fence[1] and not marker[2].strip():
                fence = None
            continue
        if marker:
            flush()
            fence = (marker[1][0], len(marker[1]))
            continue
        if not stripped:
            flush()
            in_table = in_quote = False
            continue
        if re.match(r'^ {0,3}>', line) or in_quote:
            flush()
            in_quote = True
            continue
        next_line = lines[index + 1] if index + 1 < len(lines) else ''
        if TABLE_RULE.match(next_line) or TABLE_RULE.match(line) or stripped.startswith('|'):
            flush()
            in_table = True
            continue
        if in_table and '|' in line:
            continue
        in_table = False
        if (re.match(r'^ {0,3}#{1,6}(?:\s|$)', line)
                or re.match(r'^\s*(?:=+|-+)\s*$', next_line)
                or re.match(r'^\s*(?:=+|-+|\*{3,}|_{3,})\s*$', line)
                or re.match(r'^ {0,3}\[[^\]]+\]:', line)
                or line.startswith(('    ', '\t'))):
            flush()
            continue
        # 列表项分别统计；列表编号不是正文。
        item = re.match(r'^ {0,3}(?:[-+*]|\d+[.)])\s+(.*)$', line)
        if item:
            flush()
            current.append(item[1])
        else:
            current.append(line)
    flush()
    return paragraphs


def describe(text):
    paragraphs = prose_paragraphs(text)
    sentences = []
    for paragraph in paragraphs:
        for part in re.split(r'[。？！?!]+[”’」』]*', paragraph):
            sentence = re.sub(r'\s', '', part)
            if any(char.isalnum() for char in sentence):
                sentences.append(sentence)
    count = len(sentences)
    return {
        'paragraphs': len(paragraphs),
        'sentences': count,
        'mean_commas': sum(sentence.count('，') for sentence in sentences) / count if count else None,
        'mean_length': sum(map(len, sentences)) / count if count else None,
    }


def describe_file(path):
    return {'path': str(path), **describe(path.read_text(encoding='utf-8'))}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path, help='要观察的 Markdown 稿件')
    parser.add_argument('--reference', action='append', default=[], type=Path, help='明确选定的参考稿，可重复')
    parser.add_argument('--json', action='store_true', help='输出描述统计 JSON')
    args = parser.parse_args(argv)
    try:
        result = {
            'articles': [describe_file(path) for path in args.files],
            'references': [describe_file(path) for path in args.reference],
            'note': NOTE,
        }
    except (OSError, UnicodeError) as error:
        parser.error(str(error))
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        for kind, label in (('articles', '稿件'), ('references', '指定参考')):
            for item in result[kind]:
                if item['sentences']:
                    summary = (f"{item['paragraphs']} 段，{item['sentences']} 句，"
                               f"每句 {item['mean_commas']:.2f} 个逗号，{item['mean_length']:.1f} 字符")
                else:
                    summary = '没有可统计的正文句子'
                print(f"{label} {item['path']}：{summary}")
        print(NOTE)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
