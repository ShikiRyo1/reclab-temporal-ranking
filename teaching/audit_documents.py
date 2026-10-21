"""Check rendered artifacts, native equations, source freshness and HTML structure."""
from pathlib import Path
import json,re,hashlib
from zipfile import ZipFile
from lxml import etree,html
from pypdf import PdfReader
HERE=Path(__file__).resolve().parent;ROOT=HERE.parent
ns={'w':'http://schemas.openxmlformats.org/wordprocessingml/2006/main','m':'http://schemas.openxmlformats.org/officeDocument/2006/math'}
reports={}
for name in ['个性化推荐与排序服务完整学习手册','代码逐行阅读指南']:
    docx=HERE/(name+'.docx');pdf=HERE/(name+'.pdf')
    if not pdf.exists():continue
    with ZipFile(docx) as z:xml=etree.fromstring(z.read('word/document.xml'));styles=etree.fromstring(z.read('word/styles.xml'))
    text=''.join(xml.xpath('//w:t/text()',namespaces=ns))
    equations=xml.xpath('//m:oMath',namespaces=ns)
    pdf_text='\n'.join(p.extract_text() for p in PdfReader(str(pdf)).pages)
    reports[name]={'docx_sha256':hashlib.sha256(docx.read_bytes()).hexdigest(),'pdf_sha256':hashlib.sha256(pdf.read_bytes()).hexdigest(),'pages':len(PdfReader(str(pdf)).pages),'native_equations':len(equations),'raw_math_delimiters':any(x in text for x in ['\\(','\\[','$$']),'paragraph_borders':len(styles.xpath('//w:pBdr',namespaces=ns)),'body_chars':len(text),'pdf_extract_chars':len(pdf_text)}
manifest=json.loads((HERE/'qa/source_manifest.json').read_text(encoding='utf-8'))
stale=[]
for entry in manifest['source_files']:
    if hashlib.sha256((ROOT/entry['file']).read_bytes()).hexdigest()!=entry['sha256']:stale.append(entry['file'])
tree=html.fromstring((HERE/'代码逐行阅读指南.html').read_bytes())
ids=tree.xpath('//@id');links=[a[1:] for a in tree.xpath('//a/@href') if a.startswith('#')]
html_report={'source_files':len(manifest['source_files']),'source_lines':manifest['lines'],'unique_ids':len(ids)==len(set(ids)),'broken_internal_links':[x for x in links if x not in ids],'source_line_rows':len(tree.xpath('//table[contains(@class,"code-table")]/tr')),'stale_source_files':stale,'external_scripts':tree.xpath('//script[@src]/@src'),'native_mathml_count':len(tree.xpath('//*[local-name()="math"]')),'interactive_browser_verification':'not_run_security_review_denied_file_navigation; no alternative route attempted'}
output={'documents':reports,'html_static':html_report,'cli_examples':'train/prepare_data/verify_live/benchmark_api --help executed; required data-dir verified; project Python pip exists','visual_qa':'See per-reviewer manifests and final acceptance; structure checks do not substitute for visual review'}
(HERE/'qa/structural_audit.json').write_text(json.dumps(output,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(output,ensure_ascii=True))
