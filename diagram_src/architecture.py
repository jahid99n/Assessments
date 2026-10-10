W,H=1600,1160
o=[]
def a(s):o.append(s)
COL={'front':'#DD344C','sec':'#DD344C','net':'#8C4FFF','stor':'#7AA116','comp':'#ED7100','db':'#C925D1','ml':'#01A88D','int':'#E7157B','mgmt':'#E7157B','ext':'#545B64'}
FLOW={'user':'#2563EB','proc':'#ED7100','sched':'#8C4FFF','aux':'#6B7280'}
a(f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}" font-family="Inter, DejaVu Sans, sans-serif">')
a('<defs>')
for k,c in FLOW.items():
    a(f'<marker id="m{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse"><path d="M0,0 L10,5 L0,10 z" fill="{c}"/></marker>')
a('</defs>')
a(f'<rect width="{W}" height="{H}" fill="#ffffff"/>')
a('<text x="40" y="48" font-size="28" font-weight="700" fill="#111827">Smart Expense Tracker – AWS Architecture</text>')
a('<text x="40" y="76" font-size="15" fill="#4B5563">Serverless, event-driven design · processing separated from storage · region ap-southeast-2 (Sydney)</text>')
# region box
a('<rect x="245" y="100" width="1325" height="830" rx="14" fill="#F8FAFC" stroke="#232F3E" stroke-width="1.5" stroke-dasharray="8 5"/>')
a('<rect x="245" y="100" width="300" height="30" rx="6" fill="#232F3E"/><text x="258" y="121" font-size="14" font-weight="600" fill="#fff">AWS Cloud · ap-southeast-2 (Sydney)</text>')
# tier labels
for x,t in [(290,'PRESENTATION &amp; ACCESS'),(620,'PROCESSING (Lambda)'),(970,'STORAGE &amp; AI'),(1310,'NOTIFICATION')]:
    a(f'<text x="{x}" y="158" font-size="12" font-weight="700" letter-spacing="1" fill="#6B7280">{t}</text>')
def box(x,y,w,h,cat,abbr,title,lines):
    c=COL[cat]
    a(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="10" fill="#fff" stroke="{c}" stroke-width="2"/>')
    a(f'<rect x="{x+12}" y="{y+14}" width="40" height="40" rx="8" fill="{c}"/>')
    a(f'<text x="{x+32}" y="{y+40}" font-size="{13 if len(abbr)<4 else 11}" font-weight="700" fill="#fff" text-anchor="middle">{abbr}</text>')
    a(f'<text x="{x+62}" y="{y+32}" font-size="15" font-weight="700" fill="#111827">{title}</text>')
    for i,l in enumerate(lines):
        a(f'<text x="{x+62}" y="{y+52+i*18}" font-size="12.5" fill="#374151">{l}</text>')
cx={'A':290,'B':620,'C':970,'D':1310}; cw={'A':230,'B':240,'C':250,'D':230}
ry={1:175,2:355,3:535,4:715}; BH=110
def B(col,row,*args): box(cx[col],ry[row],cw[col],BH,*args)
def mid(col,row,side):
    x,y,w=cx[col],ry[row],cw[col]
    return {'l':(x,y+BH/2),'r':(x+w,y+BH/2),'t':(x+w/2,y),'b':(x+w/2,y+BH)}[side]
# user
a('<rect x="40" y="400" width="165" height="130" rx="10" fill="#fff" stroke="#545B64" stroke-width="2"/>')
a('<circle cx="122" cy="432" r="14" fill="#545B64"/><path d="M96,470 a26,22 0 0 1 52,0 z" fill="#545B64"/>')
a('<text x="122" y="496" font-size="15" font-weight="700" text-anchor="middle" fill="#111827">User</text>')
a('<text x="122" y="515" font-size="12.5" text-anchor="middle" fill="#374151">web browser / phone</text>')
B('A',1,'front','AMP','AWS Amplify',['Hosts web dashboard','HTML · JS · Chart.js'])
B('A',2,'sec','COG','Amazon Cognito',['User pool + hosted login','issues JWT tokens'])
B('A',3,'net','API','API Gateway',['HTTP API, JWT authorizer','/expenses /stats /budget'])
B('A',4,'stor','S3','Amazon S3',['receipts/{userId}/{id}.jpg','private, encrypted'])
B('B',1,'int','EB','EventBridge Scheduler',['cron: Mon 09:00','Australia/Sydney'])
B('B',3,'comp','λ','expense-api',['AWS Lambda · all API routes','presigned upload URLs'])
B('B',4,'comp','λ','receipt-processor',['AWS Lambda · S3 trigger','parse · categorise · save'])
B('C',1,'comp','λ','weekly-summary',['AWS Lambda · scheduled','totals last 7 days per user'])
B('C',3,'db','DDB','Amazon DynamoDB',['table: Expenses','table: Budgets'])
B('C',4,'ml','TX','Amazon Textract',['AnalyzeExpense API','merchant · date · total'])
B('D',2,'int','SNS','Amazon SNS',['topic: expense-alerts','filtered per user'])
# email external
a('<rect x="1310" y="175" width="230" height="90" rx="10" fill="#fff" stroke="#545B64" stroke-width="2" stroke-dasharray="5 4"/>')
a('<text x="1425" y="212" font-size="15" font-weight="700" text-anchor="middle" fill="#111827">User email inbox</text>')
a('<text x="1425" y="234" font-size="12.5" text-anchor="middle" fill="#374151">budget alerts · weekly summary</text>')
# CloudWatch bar
a('<rect x="290" y="870" width="1250" height="44" rx="10" fill="#fff" stroke="#E7157B" stroke-width="2"/>')
a('<rect x="302" y="878" width="28" height="28" rx="6" fill="#E7157B"/><text x="316" y="897" font-size="10" font-weight="700" text-anchor="middle" fill="#fff">CW</text>')
a('<text x="342" y="897" font-size="14" fill="#111827"><tspan font-weight="700">Amazon CloudWatch</tspan>  –  logs from all Lambda functions · metrics dashboard · error alarm</text>')
def badge(x,y,n,c):
    a(f'<circle cx="{x}" cy="{y}" r="11" fill="{c}"/><text x="{x}" y="{y+4.5}" font-size="12" font-weight="700" fill="#fff" text-anchor="middle">{n}</text>')
def line(pts,k,dash=False,n=None,at=None,label=None,lat=None):
    c=FLOW[k]; d='M'+' L'.join(f'{x},{y}' for x,y in pts)
    a(f'<path d="{d}" fill="none" stroke="{c}" stroke-width="2.2" {"stroke-dasharray=\"6 4\"" if dash else ""} marker-end="url(#m{k})"/>')
    if label: a(f'<text x="{lat[0]}" y="{lat[1]}" font-size="11.5" fill="{c}" font-weight="600" text-anchor="{lat[2] if len(lat)>2 else "middle"}">{label}</text>')
    if n: badge(*at,n,c)
# user bus
bx=228
a(f'<path d="M205,465 L{bx},465" stroke="{FLOW["user"]}" stroke-width="2.2"/>')
a(f'<path d="M{bx},230 L{bx},770" stroke="{FLOW["user"]}" stroke-width="2.2"/>')
for row,n in [(1,1),(2,2),(3,3),(4,6)]:
    y=ry[row]+BH/2
    line([(bx,y),(cx['A'],y)],'user',n=n,at=(bx+30,y-14) if False else (bx+31,y))
# auth check
line([(345,ry[3]),(345,ry[2]+BH)],'aux',dash=True,label='verify JWT',lat=(352,510,'start'))
# api -> lambda
y3=ry[3]+BH/2
line([(cx['A']+cw['A'],y3),(cx['B'],y3)],'user',n=4,at=(565,y3-16))
line([(cx['B']+cw['B'],y3),(cx['C'],y3)],'user',n=5,at=(915,y3-16),label='read / write',lat=(915,y3+22))
# s3 -> processor
y4=ry[4]+BH/2
line([(cx['A']+cw['A'],y4),(cx['B'],y4)],'proc',n=7,at=(565,y4-16),label='upload event',lat=(565,y4+22))
line([(cx['B']+cw['B'],y4),(cx['C'],y4)],'proc',n=8,at=(915,y4-16),label='extract',lat=(915,y4+22))
# processor -> dynamodb
line([(800,ry[4]),(800,ry[4]-25),(1030,ry[4]-25),(1030,ry[3]+BH)],'proc',n=9,at=(800,ry[4]-12),label='save expense, check budget',lat=(915,ry[4]-34))
# processor -> sns
line([(700,ry[4]+BH),(700,850),(1500,850),(1500,ry[2]+BH)],'proc',n=10,at=(1100,850),label='over-budget alert',lat=(1180,844,'start'))
# eventbridge -> weekly
y1=ry[1]+BH/2
line([(cx['B']+cw['B'],y1),(cx['C'],y1)],'sched',n=11,at=(915,y1-16))
# weekly -> dynamodb
line([(1095,ry[1]+BH),(1095,ry[3])],'sched',n=12,at=(1095,445),label='read expenses',lat=(1112,449,'start'))
# weekly -> sns
line([(cx['C']+cw['C'],y1+20),(1265,y1+20),(1265,ry[2]+BH/2),(cx['D'],ry[2]+BH/2)],'sched',n=13,at=(1265,330))
# sns -> email
line([(1425,ry[2]),(1425,265)],'aux',n=14,at=(1440,312))
# legend
lx,ly=620,340
a(f'<rect x="{lx}" y="{ly}" width="240" height="150" rx="10" fill="#fff" stroke="#E5E7EB"/>')
a(f'<text x="{lx+14}" y="{ly+26}" font-size="13" font-weight="700" fill="#111827">Flows</text>')
for i,(k,t,dash) in enumerate([('user','User request / API',0),('proc','Receipt processing',0),('sched','Weekly summary',0),('aux','Auth · monitoring · email',1)]):
    yy=ly+50+i*26
    a(f'<path d="M{lx+14},{yy} L{lx+54},{yy}" stroke="{FLOW[k]}" stroke-width="2.5" {"stroke-dasharray=\"6 4\"" if dash else ""}/>')
    a(f'<text x="{lx+64}" y="{yy+4}" font-size="12.5" fill="#374151">{t}</text>')
# steps
steps=[('user','1','User opens the web app hosted on Amplify'),('user','2','User signs in with Cognito and receives a JWT'),('user','3','Browser calls the API with the JWT'),('user','4','API Gateway checks the JWT and invokes expense-api'),('user','5','expense-api reads/writes DynamoDB; returns a presigned S3 URL'),('user','6','Browser uploads the receipt photo straight to S3'),('proc','7','S3 upload event triggers receipt-processor'),
('proc','8','Textract AnalyzeExpense reads merchant, date, total, GST'),('proc','9','Expense saved to DynamoDB; month total compared with budget'),('proc','10','If over budget, alert published to SNS'),('sched','11','EventBridge runs weekly-summary every Monday 9am'),('sched','12','weekly-summary totals each user’s last 7 days'),('sched','13','Summary published to SNS'),('aux','14','SNS emails the user (filtered by userId)')]
a('<text x="40" y="968" font-size="15" font-weight="700" fill="#111827">Step-by-step</text>')
for i,(k,n,t) in enumerate(steps):
    col=i//5; row=i%5
    x=40+col*520; y=995+row*30
    badge(x+11,y,n,FLOW[k]); a(f'<text x="{x+30}" y="{y+5}" font-size="13" fill="#374151">{t}</text>')
a('</svg>')
open(__import__('os').path.join(__import__('os').path.dirname(__file__),'..','images','architecture.svg'),'w').write('\n'.join(o))
