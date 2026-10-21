"""Render every PDF page with bundled PDFium and retain a page audit manifest."""
import argparse,json,hashlib
from pathlib import Path
import pypdfium2 as pdfium
from PIL import Image,ImageOps,ImageDraw,ImageFont
p=argparse.ArgumentParser();p.add_argument('pdf');p.add_argument('--name',default='main');a=p.parse_args()
path=Path(a.pdf);out=path.parent/'qa'/a.name;out.mkdir(parents=True,exist_ok=True)
pdf=pdfium.PdfDocument(str(path));entries=[]
for i,page in enumerate(pdf):
    img=page.render(scale=1.5).to_pil().convert('RGB');dest=out/f'page-{i+1:03d}.png';img.save(dest)
    entries.append({'page':i+1,'image':str(dest),'width':img.width,'height':img.height})
for start in range(0,len(entries),12):
    sheet=Image.new('RGB',(4*330,3*490),'#DDDDDD');d=ImageDraw.Draw(sheet)
    for n,e in enumerate(entries[start:start+12]):
        with Image.open(e['image']) as im:
            im.thumbnail((315,450));x=(n%4)*330+(330-im.width)//2;y=(n//4)*490+25;sheet.paste(im,(x,y))
        d.text(((n%4)*330+12,(n//4)*490+5),str(e['page']),fill='black')
    sheet.save(out/f'contact-{start+1:03d}.png')
report={'pdf':str(path),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'pages':len(entries),'entries':entries,'visual_review':'pending'}
(out/'render_manifest.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
print(json.dumps({'pages':len(entries),'folder':str(out)}))
