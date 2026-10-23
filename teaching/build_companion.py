"""Build an editable line-reference guide and a fully searchable source companion."""
from pathlib import Path
import re,json,hashlib,html,csv,argparse
from docx import Document
from build_manual import configure,render_markdown,LatexParser,EQUATIONS
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--html-only',action='store_true',help='Refresh electronic index without changing a reviewed DOCX')
args=parser.parse_args()
def clean(text):
    text=re.sub(r'中文采用教学技能的既有偏好.*?认证。','',text)
    return text.replace('模型工件','模型产物').replace('服务工件','服务产物').replace('工件','产物')
def mathml(latex):
    def node(n):
        tag=n.tag.rsplit('}',1)[-1];children=list(n)
        if tag=='t':return '<mi>'+html.escape(n.text or '')+'</mi>'
        if tag in ('rPr','accPr','barPr','radPr','deg'):return ''
        bits=[node(x) for x in children]
        if tag=='f':return '<mfrac>'+''.join(bits)+'</mfrac>'
        if tag=='sSub':return '<msub>'+''.join(bits)+'</msub>'
        if tag=='sSup':return '<msup>'+''.join(bits)+'</msup>'
        if tag=='sSubSup':return '<msubsup>'+''.join(bits)+'</msubsup>'
        if tag=='acc':return '<mover>'+''.join(bits)+'<mo>~</mo></mover>'
        if tag=='bar':return '<mover>'+''.join(bits)+'<mo>¯</mo></mover>'
        if tag=='rad':return '<msqrt>'+''.join(bits)+'</msqrt>'
        return '<mrow>'+''.join(bits)+'</mrow>'
    return '<math xmlns="http://www.w3.org/1998/Math/MathML">'+''.join(node(n) for n in LatexParser(latex).sequence())+'</math>'
def inline(t):
    parts=re.split(r'(\\\(.*?\\\))',t);out=[]
    for p in parts:
        if p.startswith('\\('):out.append(mathml(p[2:-2]));continue
        p=html.escape(p);p=re.sub(r'`([^`]+)`',r'<code>\1</code>',p);p=re.sub(r'\*\*(.*?)\*\*',r'<strong>\1</strong>',p);out.append(p)
    return ''.join(out)
def markdown(t):
    t=re.sub(r'\\\[\s*(.*?)\s*\\\]',lambda m:'$$'+re.sub(r'\s+',' ',m.group(1))+'$$',t,flags=re.S)
    out=[];code=False;tab=False
    for line in t.splitlines():
        if line.startswith('```'):
            out.append('</code></pre>' if code else '<pre><code>');code=not code;continue
        if code:out.append(html.escape(line)+'\n');continue
        if line.startswith('|'):
            if re.match(r'^\|[\s|:\-]+$',line):continue
            if not tab:out.append('<table>');tab=True
            out.append('<tr>'+''.join('<td>'+inline(c.strip())+'</td>' for c in line.strip('|').split('|'))+'</tr>');continue
        if tab:out.append('</table>');tab=False
        if not line:continue
        picture=re.match(r'^!\[(.*?)\]\((.*?)\)$',line)
        if picture:
            out.append('<figure><img style="max-width:100%;height:auto" src="'+html.escape(picture[2],quote=True)+'" alt="'+html.escape(picture[1],quote=True)+'"><figcaption>'+inline(picture[1])+'</figcaption></figure>');continue
        if line.startswith('$$'):out.append('<div class="equation">'+mathml(line[2:-2])+'</div>');continue
        m=re.match(r'^(#{1,3}) (.*)',line)
        if m:out.append(f'<h{len(m[1])}>{inline(m[2])}</h{len(m[1])}>')
        else:out.append('<p>'+inline(line)+'</p>')
    if tab:out.append('</table>')
    return ''.join(out)

files=[HERE/'chapters_code_model.md',HERE/'chapters_code_service.md',HERE/'chapters_code_tests_model.md']
if (HERE/'chapters_code_baseline.md').exists():files.append(HERE/'chapters_code_baseline.md')
intro='# 代码逐行阅读指南\n\n本伴册按文件与实际行号解释每段代码。可搜索HTML还包含完整原代码、逐行编号和源码指纹；Word保留精炼的逻辑伴读，避免把相同大代码块印两遍。遇到L20–L28，先在HTML找到该文件的这些行，再读对应说明。空行与单独闭括号归入所属语句。主手册负责原理、操作、实测和求职表达。\n\n'
source=intro+'\n\n'.join(clean(p.read_text(encoding='utf-8')) for p in files)
out=HERE/'代码逐行阅读指南.docx'
if not args.html_only:
    doc=Document();configure(doc);doc.core_properties.title='代码逐行阅读指南';render_markdown(doc,source);doc.save(out)
(HERE/'代码逐行阅读指南_源稿.md').write_text(source,encoding='utf-8')
paths=sorted(list((ROOT/'src').rglob('*.py'))+list((ROOT/'src').rglob('*.html'))+list((ROOT/'scripts').glob('*.py'))+list((ROOT/'tests').glob('*.py'))+list((ROOT/'baseline').glob('*.py')))
paths += [ROOT/x for x in ['Dockerfile','compose.yaml','pyproject.toml','requirements-lock.txt','requirements-api.txt','configs/temporal_1m.json','docs/ci-template.yml','baseline/setup.ps1','baseline/requirements-lock.txt']]
electronic_notes=HERE/'chapters_code_http_audit.md'
electronic_source=source
if electronic_notes.exists():
    electronic_source+='\n\n'+electronic_notes.read_text(encoding='utf-8')
    paths.append(ROOT/'reports/release/verify_api_contract_20261022.py')
manifest=[];raw=[]
for p in paths:
    if not p.exists():continue
    rel=p.relative_to(ROOT).as_posix();data=p.read_text(encoding='utf-8-sig');lines=data.splitlines();anchor='source-'+re.sub('[^a-zA-Z0-9]','-',rel)
    manifest.append({'file':rel,'lines':len(lines),'sha256':hashlib.sha256(p.read_bytes()).hexdigest(),'anchor':anchor})
    raw.append('<section class="source" id="'+anchor+'"><h2>'+html.escape(rel)+'</h2><p>SHA256: '+manifest[-1]['sha256']+'</p><table class="code-table">')
    for n,line in enumerate(lines,1):raw.append('<tr id="'+anchor+'-L'+str(n)+'"><td class="line">'+str(n)+'</td><td><pre>'+html.escape(line)+'</pre></td></tr>')
    raw.append('</table></section>')
toc=''.join('<a href="#'+x['anchor']+'">'+x['file']+'</a>' for x in manifest)
css='body{font:16px/1.7 "Microsoft YaHei",system-ui,sans-serif;margin:0;color:#18232f;background:#fff}main{max-width:1100px;margin:0 auto;padding:32px}h1,h2,h3{color:#111;line-height:1.35}h2{margin-top:40px}p{margin:14px 0}code,pre{font:13px/1.6 Consolas,monospace}pre{white-space:pre-wrap;overflow-wrap:anywhere;margin:0}table{border-collapse:collapse;width:100%;font-size:14px}td{padding:8px;border:1px solid #ddd;vertical-align:top}tr:nth-child(even){background:#f7f9fa}.line{width:45px;color:#64748b;text-align:right}nav{position:sticky;top:0;padding:10px;background:#eef3f6;z-index:1}nav a{margin:0 16px 0 0;color:#124b72}input{padding:8px;width:340px}details a{display:block}math{font-size:1.12em}.equation{text-align:center;margin:24px 0}.code-table td{padding:2px 8px}.source{margin-top:45px}mark{background:#ffe282}button{padding:8px;margin-left:8px}'
page='<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>代码逐行阅读指南</title><style>'+css+'</style><nav><a href="#guide">伴读说明</a><a href="#sources">完整源码</a><input id="query" placeholder="输入关键字，按 Enter 搜索"><button id="find">查找下一处</button></nav><main id="guide">'+markdown(electronic_source)+'<h1 id="sources">完整源码与真实行号</h1><details open><summary>选择文件</summary>'+toc+'</details>'+''.join(raw)+'</main><script>function next(){const q=document.getElementById("query").value;if(q)window.find(q,false,false,true,false,false,false)}document.getElementById("find").onclick=next;document.getElementById("query").onkeydown=e=>{if(e.key==="Enter")next()};</script></html>'
(HERE/'代码逐行阅读指南.html').write_text(page,encoding='utf-8')
(HERE/'qa'/'source_manifest.json').write_text(json.dumps({'source_files':manifest,'lines':sum(x['lines'] for x in manifest),'guide_sources':[p.name for p in files],'electronic_guide_sources':[electronic_notes.name] if electronic_notes.exists() else [],'docx_sha256':hashlib.sha256(out.read_bytes()).hexdigest()},indent=2),encoding='utf-8')
shots=[('01_upstream_commit.png','https://github.com/recommenders-team/recommenders/tree/aa8332189cd495be6ffaa7e1c8054f1c180b5ef3','打开固定commit代码页'),('02_personalized.png','http://127.0.0.1:8011','输入1161/10/全部类别/自动权重，生成推荐'),('03_cold_drama.png','http://127.0.0.1:8011','空用户/Drama类别，生成推荐'),('04_request_response.png','http://127.0.0.1:8011','展开请求与响应JSON'),('05_swagger_execute.png','http://127.0.0.1:8011/docs','展开POST，Try it out，输入JSON，Execute'),('06_swagger_200.png','http://127.0.0.1:8011/docs','查看合法请求Server response 200'),('07_swagger_422.png','http://127.0.0.1:8011/docs','k=51执行后查看422'),('08_github_published.png','https://github.com/ShikiRyo1/reclab-temporal-ranking','打开已发布仓库首页')]
index_path=HERE/'screenshots'/'index.csv'
# Rebuilding teaching must not erase captured provenance or later audit metadata.
fields=['file','url','action','sha256','kind'];previous={}
if index_path.exists():
    with index_path.open(encoding='utf-8-sig',newline='') as f:
        reader=csv.DictReader(f)
        fields+= [key for key in (reader.fieldnames or []) if key not in fields]
        previous={row['file']:row for row in reader}
updated_rows=[]
for name,url,action in shots:
    row=previous.get(name,{})
    current_sha=hashlib.sha256((HERE/'screenshots'/name).read_bytes()).hexdigest()
    if row.get('sha256') and row['sha256']!=current_sha:
        raise ValueError(f'Screenshot changed; re-audit provenance before rebuilding: {name}')
    row.update(file=name,url=url,action=action,sha256=current_sha,kind='真实浏览器运行截图')
    updated_rows.append(row)
# Preserve additional audit captures instead of silently dropping non-original rows.
for name,row in previous.items():
    if name in {item[0] for item in shots}:continue
    path=HERE/'screenshots'/name
    if row.get('sha256') and hashlib.sha256(path.read_bytes()).hexdigest()!=row['sha256']:
        raise ValueError(f'Additional screenshot changed: {name}')
    updated_rows.append(row)
with index_path.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(updated_rows)
print(json.dumps({'docx':str(out),'files':len(manifest),'source_lines':sum(x['lines'] for x in manifest),'equations':len(EQUATIONS)},ensure_ascii=False))
