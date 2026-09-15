import re

import bleach
from django import template
from django.utils.safestring import mark_safe

register = template.Library()

ALLOWED_TAGS = [
    'div', 'p', 'br', 'strong', 'em', 'code', 'pre', 'ul', 'ol', 'li',
    'blockquote', 'a', 'h2', 'h3', 'hr',
]
ALLOWED_ATTRS = {
    '*': ['class'],
    'a': ['href', 'title', 'rel', 'target', 'class'],
}


def _preserve_spaces(text):
    text = text.replace('\t', '    ')
    return re.sub(r' {2,}', lambda match: '&nbsp;' * len(match.group(0)), text)


def _inline_markup(text):
    text = bleach.clean(text, tags=[], strip=True)
    text = _preserve_spaces(text)
    text = re.sub(
        r'`([^`]+)`',
        r'<code class="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[0.9em] text-slate-800">\1</code>',
        text,
    )
    text = re.sub(
        r'\[([^\]]+)\]\((https?://[^\s)]+)\)',
        r'<a href="\2" target="_blank" rel="noopener noreferrer" class="font-semibold text-brand-purple underline decoration-violet-200 underline-offset-2 hover:decoration-brand-purple">\1</a>',
        text,
    )
    text = re.sub(r'\*\*([^*]+)\*\*', r'<strong>\1</strong>', text)
    text = re.sub(r'(?<!\*)\*([^*]+)\*(?!\*)', r'<em>\1</em>', text)
    return text


@register.filter(name='guide_markdown')
def guide_markdown(value):
    """Render safe, readable guide markup while retaining line breaks and spacing."""
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
            html.append(
                '<div class="my-3 leading-7 text-slate-700">'
                f'<p>{rendered_lines}</p></div>'
            )
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
                code = bleach.clean('\n'.join(code_lines), tags=[], strip=True)
                html.append(
                    '<pre class="my-4 overflow-x-auto rounded-xl bg-slate-900 p-4 text-sm leading-6 text-slate-100">'
                    f'<code class="font-mono">{code}</code></pre>'
                )
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

        heading = re.match(r'^(#{2,3})\s+(.+)$', stripped)
        if heading:
            flush_paragraph()
            close_list()
            if len(heading.group(1)) == 2:
                html.append(
                    f'<h2 class="mb-2 mt-6 text-xl font-extrabold leading-snug text-slate-900">'
                    f'{_inline_markup(heading.group(2))}</h2>'
                )
            else:
                html.append(
                    f'<h3 class="mb-2 mt-5 text-base font-extrabold leading-snug text-slate-900">'
                    f'{_inline_markup(heading.group(2))}</h3>'
                )
            continue

        if stripped == '---':
            flush_paragraph()
            close_list()
            html.append('<hr class="my-5 border-0 border-t border-slate-200">')
            continue

        if stripped.startswith('> '):
            flush_paragraph()
            close_list()
            html.append(
                '<blockquote class="my-4 rounded-r-xl border-l-4 border-violet-400 '
                'bg-violet-50 px-4 py-3 leading-7 text-violet-950">'
                f'{_inline_markup(stripped[2:])}</blockquote>'
            )
            continue

        bullet = re.match(r'^[-*]\s+(.+)$', stripped)
        ordered = re.match(r'^\d+[.)]\s+(.+)$', stripped)
        if bullet or ordered:
            flush_paragraph()
            wanted = 'ul' if bullet else 'ol'
            if list_type != wanted:
                close_list()
                list_class = (
                    'my-3 ml-5 list-disc space-y-1 text-slate-700'
                    if wanted == 'ul'
                    else 'my-3 ml-5 list-decimal space-y-1 text-slate-700'
                )
                html.append(f'<{wanted} class="{list_class}">')
                list_type = wanted
            html.append(f'<li class="pl-1 leading-7 marker:font-bold marker:text-violet-600">{_inline_markup((bullet or ordered).group(1))}</li>')
            continue

        close_list()
        paragraph.append(line.rstrip())

    if in_code:
        code = bleach.clean('\n'.join(code_lines), tags=[], strip=True)
        html.append(
            '<pre class="my-4 overflow-x-auto rounded-xl bg-slate-900 p-4 text-sm leading-6 text-slate-100">'
            f'<code class="font-mono">{code}</code></pre>'
        )
    flush_paragraph()
    close_list()
    cleaned = bleach.clean(''.join(html), tags=ALLOWED_TAGS, attributes=ALLOWED_ATTRS, strip=True)
    return mark_safe(cleaned)
