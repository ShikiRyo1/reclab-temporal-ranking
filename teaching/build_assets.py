"""Draw teaching-only diagrams; these are not execution screenshots."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
HERE=Path(__file__).resolve().parent
OUT=HERE/'assets';OUT.mkdir(exist_ok=True)
FONT='C:/Windows/Fonts/msyh.ttc'
def canvas(title, h=600):
    im=Image.new('RGB',(1600,h),'white');d=ImageDraw.Draw(im)
    d.text((45,25),title,font=ImageFont.truetype(FONT,35),fill='#12243B')
    return im,d
def box(d,xy,title,lines,color='#E7EFF8'):
    d.rounded_rectangle(xy,radius=10,fill=color,outline='#6482A3',width=2)
    x,y,_,_=xy;d.text((x+18,y+18),title,font=ImageFont.truetype(FONT,28),fill='#12243B')
    for n,t in enumerate(lines):d.text((x+18,y+65+n*36),t,font=ImageFont.truetype(FONT,23),fill='#26384A')
def arrow(d,a,b):
    d.line([a,b],fill='#385C81',width=5);x,y=b
    d.polygon([(x,y),(x-14,y-8),(x-14,y+8)],fill='#385C81')
im,d=canvas('从评分日志到可验证的推荐服务 / Data → decision → service',650)
boxes=[(40,130,375,340),(435,130,770,340),(830,130,1165,340),(1225,130,1560,340)]
texts=[('数据与协议',['MovieLens 评分','时间切分 / 正反馈','候选与已见过滤']),('模型与评估',['Popularity / SAR / BPR','验证集选择重排','测试集 + 不确定性']),('模型产物',['因子 / ID 映射','历史 / 类型 / 版本','artifact 校验']),('HTTP 与网页',['输入验证 / 回退','Docker / health','真实请求与负载'])]
for xy,(t,ls) in zip(boxes,texts):box(d,xy,t,ls)
for a,b in zip(boxes,boxes[1:]):arrow(d,(a[2]+8,235),(b[0]-8,235))
box(d,(120,420,1480,570),'贯穿全程的证据链',['固定数据与代码 → 保存配置和报告 → 比对模型与服务输出 → 记录限制与回滚方式'],'#F1F5F0')
im.save(OUT/'system_flow.png')
im,d=canvas('全局时间切分 / 一个统一的历史边界',620)
parts=[((45,145,760,330),'训练 Train',['700,148 条评分','截止 2000-11-22 03:06:26 UTC']),((775,145,1150,330),'验证 Validation',['150,029 条','截止 2000-12-10']),((1165,145,1555,330),'测试 Test',['150,032 条','验证截止之后'])]
for xy,t,ls in parts:box(d,xy,t,ls)
arrow(d,(50,380),(1540,380))
d.text((50,405),'模型和目录在训练截止时冻结；只在验证集选择 w = 0.2。',font=ImageFont.truetype(FONT,28),fill='#12243B')
d.text((50,455),'验证排除训练全部评分；测试再排除验证期已评分物品。相同时间戳不跨集合。',font=ImageFont.truetype(FONT,27),fill='#26384A')
d.text((50,510),'服务快照：仅训练历史。离线测试：额外应用验证历史过滤。二者要分别说明。',font=ImageFont.truetype(FONT,27),fill='#26384A')
im.save(OUT/'temporal_split.png')
im,d=canvas('NDCG 手算 / 相关集合 {A, C}，推荐列表 [B, A, C]',650)
for idx,(item,rel,discount) in enumerate([('B',0,'1.0000'),('A',1,'0.6309'),('C',1,'0.5000')]):
    x=60+idx*510;box(d,(x,130,x+450,360),f'位置 {idx+1}  |  电影 {item}',[f'相关性 rel = {rel}',f'位置折扣 = {discount}',f'贡献 = {float(discount)*rel:.4f}'])
d.text((65,410),'实际 DCG = 0 + 0.6309 + 0.5000 = 1.1309',font=ImageFont.truetype(FONT,30),fill='#12243B')
d.text((65,460),'理想 IDCG = 1 + 0.6309 = 1.6309',font=ImageFont.truetype(FONT,30),fill='#12243B')
d.text((65,510),'NDCG = 1.1309 / 1.6309 ≈ 0.6934；Recall = 2 / 2 = 1',font=ImageFont.truetype(FONT,30),fill='#12243B')
im.save(OUT/'metrics_example.png')
print('Created 3 labelled teaching diagrams.')
