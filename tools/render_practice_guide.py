"""Render the local Markdown practice workbook as a self-contained printable guide."""
from html import escape
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def inline(value):
    value=escape(value)
    value=re.sub(r'`([^`]+)`',r'<code>\1</code>',value)
    return re.sub(r'\*\*([^*]+)\*\*',r'<strong>\1</strong>',value)


def render():
    lines=(ROOT/'practice/Practice-Guide.md').read_text(encoding='utf-8').splitlines()
    blocks,toc=[],[]
    i=0
    while i<len(lines):
        line=lines[i].strip()
        if not line:
            i+=1;continue
        if line.startswith('# '):
            i+=1;continue
        if line.startswith('## '):
            title=line[3:]
            anchor='lesson-'+str(len(toc)+1)
            toc.append((anchor,title))
            blocks.append(f'<h2 id="{anchor}">{inline(title)}</h2>')
            i+=1;continue
        if line.startswith('|'):
            rows=[]
            while i<len(lines) and lines[i].strip().startswith('|'):
                cells=[c.strip() for c in lines[i].strip().strip('|').split('|')]
                if not all(re.fullmatch(r':?-+:?',c) for c in cells):
                    rows.append(cells)
                i+=1
            header='<thead><tr>'+''.join('<th>'+inline(c)+'</th>' for c in rows[0])+'</tr></thead>'
            body='<tbody>'+''.join('<tr>'+''.join('<td>'+inline(c)+'</td>' for c in row)+'</tr>' for row in rows[1:])+'</tbody>'
            blocks.append('<div class="table-wrap"><table>'+header+body+'</table></div>')
            continue
        if re.match(r'^\d+\. ',line):
            items=[]
            while i<len(lines) and re.match(r'^\d+\. ',lines[i].strip()):
                items.append('<li>'+inline(re.sub(r'^\d+\. ','',lines[i].strip()))+'</li>');i+=1
            blocks.append('<ol>'+''.join(items)+'</ol>');continue
        paragraph=[]
        while i<len(lines) and lines[i].strip() and not lines[i].strip().startswith(('## ','|')) and not re.match(r'^\d+\. ',lines[i].strip()):
            paragraph.append(lines[i].strip());i+=1
        blocks.append('<p>'+inline(' '.join(paragraph))+'</p>')
    contents=''.join(f'<a href="#{anchor}">{escape(title)}</a>' for anchor,title in toc)
    html='''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Mobile Desk — complete practice workbook</title><style>
    :root{--ink:#183b32;--muted:#5e726b;--green:#256448;--line:#d9e5df}*{box-sizing:border-box}html{scroll-behavior:smooth;scroll-padding-top:24px}body{margin:0;background:#f5f7f3;color:var(--ink);font:16px/1.7 "Segoe UI",Arial,sans-serif}header{background:#173e34;color:white;padding:42px max(26px,calc((100vw - 1300px)/2))}header small{color:#bfe2cc;letter-spacing:.12em;font-weight:700}h1{font-size:38px;line-height:1.2;margin:10px 0 18px;max-width:850px}header p{max-width:900px;color:#e0ebe4;margin:0}header .flow{display:flex;flex-wrap:wrap;gap:9px;margin-top:22px;font-size:14px}.flow span{border:1px solid #568574;border-radius:7px;padding:5px 12px}.layout{max-width:1380px;margin:auto;display:grid;grid-template-columns:290px 1fr;gap:36px;padding:28px}nav{position:sticky;top:20px;align-self:start;max-height:calc(100vh - 40px);overflow:auto;background:#fff;border:1px solid var(--line);border-radius:12px;padding:18px}nav summary{font-weight:700;cursor:pointer}nav a{display:block;text-decoration:none;color:#406557;padding:7px 0;font-size:13px;line-height:1.4;border-bottom:1px solid #edf2ee}nav a:hover{color:#123f2a}main{background:#fff;border:1px solid var(--line);border-radius:12px;padding:30px 38px;min-width:0}h2{font-size:24px;line-height:1.4;color:#173e34;margin:42px 0 16px;padding-top:14px;border-top:2px solid #e0ebe4;break-after:avoid}h2:first-of-type{margin-top:0;border-top:0}p{margin:14px 0}strong{color:#164d35}code{font:13px/1.6 Consolas,monospace;background:#eef4ed;padding:2px 5px;border-radius:4px;overflow-wrap:anywhere}.table-wrap{overflow-x:auto;margin:20px 0}table{width:100%;border-collapse:collapse;font-size:14px;line-height:1.6}th{text-align:left;background:#e9f1e8;color:#204d36;padding:11px 12px}td{padding:10px 12px;border-bottom:1px solid #dde8df;vertical-align:top}tbody tr:nth-child(even){background:#f8faf7}ol{padding-left:24px}li{padding:3px 0}.notice{background:#fff0cc;padding:16px 18px;border-radius:8px;border-left:4px solid #af872b;margin-bottom:24px;font-size:15px}.footer{color:#64786d;font-size:13px;border-top:1px solid var(--line);margin-top:32px;padding-top:16px}@media(max-width:1000px){.layout{grid-template-columns:1fr;padding:16px}nav{position:static;max-height:260px}main{padding:24px}h1{font-size:30px}}@media print{body{background:white;color:black;font-size:10pt;line-height:1.45}header{background:white;color:black;padding:0 0 12pt}header small,header p{color:#333}header h1{font-size:22pt}header .flow,nav{display:none}.layout{display:block;margin:0;padding:0}main{border:0;border-radius:0;padding:0}h2{font-size:16pt;margin-top:22pt;padding-top:10pt}p{margin:8pt 0}code{font-size:9pt}.table-wrap{overflow:visible}table{font-size:9pt}th,td{padding:5pt 6pt}tr{break-inside:avoid}thead{display:table-header-group}.notice{background:white;border:1px solid #888;border-left:3px solid #888;padding:8pt}@page{size:A4;margin:16mm 14mm}}
    </style></head><body><header><small>MOBILE DESK 1.6.0 · PRACTICE WORKBOOK</small><h1>A complete trading day,<br>from the first opening to recovery.</h1><p>39 guided lessons. Enter fictional examples yourself, compare verified figures, then practice extra cases from saved backup points.</p><div class="flow"><span>Catalogue &amp; products</span><span>Purchases &amp; stock</span><span>Sales &amp; original costs</span><span>Money &amp; outstanding balances</span><span>Reports, undo &amp; recovery</span></div></header><div class="layout"><nav><details open><summary>Lessons &amp; exercises</summary>'''+contents+r'''</details></nav><main><div class="notice"><strong>Open Start-Practice.cmd.</strong> Confirm Settings → Shop → Data folder points to <code>shop-data</code> inside the practice folder. These examples do not belong in the client's normal shop. Use your own practice password. All dates/prices/rates are fictional training inputs.</div>'''+''.join(blocks)+'''<p class="footer">Printable offline guide. Use Ctrl+P to print or save a PDF. Expected amounts were checked against the Mobile Desk calculation engine in an isolated temporary shop; the verification checks never populate your own shop records.</p></main></div></body></html>'''
    target=ROOT/'practice/Practice-Guide.html'
    target.write_text(html,encoding='utf-8')
    assert len(toc)==39 and html.count('<table>')==14,(len(toc),html.count('<table>'))
    print(f'Rendered {len(toc)} lessons: {target}')


if __name__=='__main__':
    render()


