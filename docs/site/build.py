#!/usr/bin/env python3
import os
import re
from pathlib import Path

SITE_DIR = Path(__file__).parent
PROJECT_ROOT = SITE_DIR.parent.parent
ASSETS_DIR = SITE_DIR / "assets"


def md_to_html(md_content):
    lines = md_content.split('\n')
    in_code_block = False
    code_lang = ''
    html_parts = []

    for line in lines:
        if line.strip().startswith('```'):
            if in_code_block:
                html_parts.append('</code></pre>')
                in_code_block = False
                code_lang = ''
            else:
                in_code_block = True
                code_lang = line.strip()[3:]
                html_parts.append(f'<pre><code class="language-{code_lang}">')
            continue

        if in_code_block:
            html_parts.append(html_escape(line))
            continue

        if line.strip() == '':
            continue

        if line.startswith('###### '):
            html_parts.append(f'<h6>{line[7:]}</h6>')
        elif line.startswith('##### '):
            html_parts.append(f'<h5>{line[6:]}</h5>')
        elif line.startswith('#### '):
            html_parts.append(f'<h4>{line[5:]}</h4>')
        elif line.startswith('### '):
            html_parts.append(f'<h3>{line[4:]}</h3>')
        elif line.startswith('## '):
            html_parts.append(f'<h2>{line[3:]}</h2>')
        elif line.startswith('# '):
            html_parts.append(f'<h1>{line[2:]}</h1>')
        elif line.startswith('---'):
            html_parts.append('<hr>')
        elif line.startswith('|') and '|' in line.strip()[1:]:
            if not html_parts or html_parts[-1].startswith('<table'):
                html_parts.append('<table>')
            parts = [p.strip() for p in line.strip().strip('|').split('|')]
            if all(set(p).issubset(set('-:| ')) for p in parts):
                continue
            if html_parts[-1] == '<table>' and all(set(p).issubset(set('-:| ')) for p in parts):
                html_parts.append('<thead><tr>' + ''.join(f'<th>{p}</th>' for p in parts) + '</tr></thead><tbody>')
            else:
                html_parts.append('<tr>' + ''.join(f'<td>{p}</td>' for p in parts) + '</tr>')
        else:
            html_parts.append(f'<p>{inline_md(line)}</p>')

    html = '\n'.join(html_parts)
    html = re.sub(r'</table>\s*<tbody>', '</thead><tbody>', html)
    html = re.sub(r'<table>\s*<tr>(.*?)</tr>\s*<tr>(.*?)</tr>',
                  r'<table><thead><tr>\1</tr></thead><tbody><tr>\2</tr>', html)
    html = re.sub(r'(<table>.*?<tbody>.*?)(</table>)', r'\1</tbody>\2', html, flags=re.DOTALL)

    return html


def inline_md(text):
    text = re.sub(r'\*\*\*(.+?)\*\*\*', r'<strong><em>\1</em></strong>', text)
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)', r'<em>\1</em>', text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)

    text = re.sub(r'> ⚠️ (.+)', r'<blockquote>⚠️ \1</blockquote>', text)
    text = re.sub(r'> 📋 (.+)', r'<blockquote>📋 \1</blockquote>', text)

    return text


def html_escape(text):
    return (text.replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;'))


def get_sidebar(current_page):
    pages = [
        ('index', '概述'),
        ('quickstart', '快速入门'),
        ('architecture', '架构说明'),
        ('api-reference', 'API 参考'),
    ]

    links = []
    for id_, name in pages:
        active = 'active' if id_ == current_page else ''
        href = f'{id_}.html' if id_ != 'index' else 'index.html'
        links.append(f'<li><a href="{href}" class="{active}">{name}</a></li>')

    return '\n'.join(links)


def build_page(title, subtitle, content_html, current_page):
    sidebar_links = get_sidebar(current_page)

    return f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title} - ShipSmith 文档</title>
  <link rel="stylesheet" href="assets/style.css">
</head>
<body>
  <div class="layout">
    <aside class="sidebar">
      <div class="sidebar-header">
        <h1>ShipSmith</h1>
        <p>部署自动化 + Feature Flag 控制平面</p>
      </div>
      <nav class="nav">
        <div class="nav-section">
          <div class="nav-section-title">文档</div>
          <ul class="nav-links">
{sidebar_links}
          </ul>
        </div>
      </nav>
    </aside>
    <main class="main">
      <div class="content">
        <h1 class="page-title">{title}</h1>
        <p class="page-desc">{subtitle}</p>
        <article>
{content_html}
        </article>
      </div>
    </main>
  </div>
</body>
</html>
'''


def main():
    ASSETS_DIR.mkdir(parents=True, exist_ok=True)

    style_src = SITE_DIR / 'assets' / 'style.css'
    if style_src.exists():
        print(f'CSS: {style_src} (already exists)')

    pages = [
        {
            'id': 'index',
            'title': '概述',
            'subtitle': 'ShipSmith 项目概览',
            'source': PROJECT_ROOT / 'README.md',
        },
        {
            'id': 'quickstart',
            'title': '快速入门',
            'subtitle': '5 分钟内搭建 ShipSmith',
            'source': PROJECT_ROOT / 'docs' / 'user-guide' / 'quickstart.md',
        },
        {
            'id': 'architecture',
            'title': '架构说明',
            'subtitle': '了解 ShipSmith 的系统设计',
            'source': PROJECT_ROOT / 'docs' / 'user-guide' / 'architecture.md',
        },
        {
            'id': 'api-reference',
            'title': 'API 参考',
            'subtitle': '完整的 API 文档',
            'source': PROJECT_ROOT / 'docs' / 'user-guide' / 'api-reference.md',
        },
    ]

    for page in pages:
        if page['source'].exists():
            md_content = page['source'].read_text(encoding='utf-8')
        else:
            md_content = f'# {page["title"]}\n\n文档正在整理中...'

        html_content = md_to_html(md_content)
        html_page = build_page(page['title'], page['subtitle'], html_content, page['id'])

        output_file = SITE_DIR / f"{page['id']}.html"
        output_file.write_text(html_page, encoding='utf-8')
        print(f'Built: {output_file.name}')

    print()
    print('To preview, run:')
    print(f'  cd {SITE_DIR}')
    print('  python3 -m http.server 8080')
    print()
    print('Then open: http://localhost:8080')


if __name__ == '__main__':
    main()
