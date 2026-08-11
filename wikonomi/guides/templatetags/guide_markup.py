import re

import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = ['p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li', 'blockquote', 'a']
ALLOWED_ATTRS = {'a': ['href', 'title', 'rel', 'target']}


def _preserve_spaces(text):
    text = text.replace('\t', '    ')
    return re.sub(r' {2,}', lambda match: '&nbsp;' * len(match.group(0)), text)


def _inline_markup(text):
    text = bleach.clean(text, tags=[], strip=True)
    text = _preserve_spaces(text)
    text = re.sub(r'`([^`]+)`', r'<code>\1</code>', text)
    text = re.sub(r'\[([^\]]+)\]\((https?://[^\s)]+)\)', r'<a href="\2" target="_blank" rel="noopener noreferrer">\1</a>', text)
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
    return text


@register.filter(name='guide_markdown')
def guide_markdown(value):
    """Render safe guide markup while retaining paragraphs, line breaks, and spacing."""
    if not value:
        return ''

    lines = str(value).replace('\r\n', '\n').replace('\r', '\n').split('\n')
    html = []
    list_type = None
    paragraph = []
    in_code = False
    code_lines = []

    def flush_paragraph():
        if paragraph:
            rendered_lines = '<br>'.join(_inline_markup(line) for line in paragraph)
            html.append(f'<p>{rendered_lines}</p>')
            paragraph.clear()

    def close_list():
        nonlocal list_type
        if list_type:
            html.append(f'</{list_type}>')
            list_type = None

    for line in lines:
        stripped = line.strip()
        if stripped.startswith('```'):
            if in_code:
                html.append('<pre><code>{}</code></pre>'.format(bleach.clean('\n'.join(code_lines), tags=[], strip=True)))
                code_lines = []
                in_code = False
            else:
                flush_paragraph()
                close_list()
                in_code = True
            continue
        if in_code:
            code_lines.append(line)
            continue
        if not stripped:
            flush_paragraph()
            close_list()
            continue
        if stripped.startswith('> '):
            flush_paragraph()
            close_list()
            html.append(f'<blockquote>{_inline_markup(stripped[2:])}</blockquote>')
            continue
        bullet = re.match(r'^[-*]\s+(.+)$', stripped)
        ordered = re.match(r'^\d+[.)]\s+(.+)$', stripped)
        if bullet or ordered:
            flush_paragraph()
            wanted = 'ul' if bullet else 'ol'
            if list_type != wanted:
                close_list()
                html.append(f'<{wanted}>')
                list_type = wanted
            html.append(f'<li>{_inline_markup((bullet or ordered).group(1))}</li>')
            continue
        close_list()
        paragraph.append(line.rstrip())

    if in_code:
        html.append('<pre><code>{}</code></pre>'.format(bleach.clean('\n'.join(code_lines), tags=[], strip=True)))
    flush_paragraph()
    close_list()
    cleaned = bleach.clean(''.join(html), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    return mark_safe(cleaned)
