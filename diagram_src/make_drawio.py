"""Generate architecture.drawio (diagrams.net XML) for the Smart Expense Tracker."""
import os
from xml.sax.saxutils import escape

cells = []
nid = [1]


def new_id():
    nid[0] += 1
    return f"n{nid[0]}"


def vertex(value, style, x, y, w, h, parent="1", vid=None):
    vid = vid or new_id()
    cells.append(f'<mxCell id="{vid}" value="{escape(value, {chr(34): "&quot;"})}" style="{style}" vertex="1" parent="{parent}">'
                 f'<mxGeometry x="{x}" y="{y}" width="{w}" height="{h}" as="geometry"/></mxCell>')
    return vid


def edge(src, dst, color, label="", dashed=False, points=(), exit=None, entry=None, pos=None):
    style = (f"edgeStyle=orthogonalEdgeStyle;rounded=1;html=1;endArrow=block;endFill=1;strokeWidth=2;"
             f"strokeColor={color};fontColor={color};fontStyle=1;fontSize=11;labelBackgroundColor=#ffffff;")
    if dashed:
        style += "dashed=1;"
    if exit:
        style += f"exitX={exit[0]};exitY={exit[1]};exitDx=0;exitDy=0;"
    if entry:
        style += f"entryX={entry[0]};entryY={entry[1]};entryDx=0;entryDy=0;"
    pts = "".join(f'<mxPoint x="{x}" y="{y}"/>' for x, y in points)
    arr = f'<Array as="points">{pts}</Array>' if pts else ""
    geo_x = f'x="{pos}" ' if pos is not None else ""
    cells.append(f'<mxCell id="{new_id()}" value="{escape(label)}" style="{style}" edge="1" parent="1" source="{src}" target="{dst}">'
                 f'<mxGeometry {geo_x}relative="1" as="geometry">{arr}</mxGeometry></mxCell>')


def aws(res, color, label, x, y):
    style = (f"sketch=0;outlineConnect=0;fontColor=#232F3E;fillColor={color};strokeColor=#ffffff;dashed=0;"
             f"verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;"
             f"shape=mxgraph.aws4.resourceIcon;resIcon=mxgraph.aws4.{res};")
    return vertex(label, style, x, y, 64, 64)


BLUE, ORANGE, PURPLE, GREY = "#2563EB", "#ED7100", "#8C4FFF", "#6B7280"

# Title
vertex("<b style='font-size:22px'>Smart Expense Tracker – AWS Architecture</b><br>"
       "Serverless, event-driven · processing separated from storage · ap-southeast-2 (Sydney)",
       "text;html=1;align=left;verticalAlign=top;fontSize=13;fontColor=#374151;", 40, 20, 900, 60)

# AWS Cloud + Region groups
vertex("AWS Cloud", "points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=1;"
       "container=0;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_aws_cloud_alt;"
       "strokeColor=#232F3E;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#232F3E;dashed=0;",
       230, 100, 1300, 820)
vertex("Region: ap-southeast-2 (Sydney)", "points=[];outlineConnect=0;gradientColor=none;html=1;whiteSpace=wrap;fontSize=12;fontStyle=0;"
       "container=0;pointerEvents=0;collapsible=0;recursiveResize=0;shape=mxgraph.aws4.group;grIcon=mxgraph.aws4.group_region;"
       "strokeColor=#00A4A6;fillColor=none;verticalAlign=top;align=left;spacingLeft=30;fontColor=#147EBA;dashed=1;",
       250, 140, 1260, 760)

# Tier labels
for x, t in [(290, "PRESENTATION &amp; ACCESS"), (600, "PROCESSING (Lambda)"), (920, "STORAGE &amp; AI"), (1250, "NOTIFICATION")]:
    vertex(f"<b>{t}</b>", "text;html=1;align=left;fontSize=11;fontColor=#6B7280;", x, 175, 220, 20)

# User
user = vertex("<b>User</b><br>web browser / phone",
              "sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;fillColor=#232F3D;strokeColor=none;dashed=0;"
              "verticalLabelPosition=bottom;verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;aspect=fixed;"
              "pointerEvents=1;shape=mxgraph.aws4.user;", 80, 470, 64, 64)

# Column x (icon left) and row y (icon top)
A, Bc, C, D = 330, 650, 970, 1300
R1, R2, R3, R4 = 220, 400, 580, 760

amplify = aws("amplify", "#DD344C", "<b>AWS Amplify</b><br>hosts web dashboard", A, R1)
cognito = aws("cognito", "#DD344C", "<b>Amazon Cognito</b><br>user pool, JWT tokens", A, R2)
apigw = aws("api_gateway", "#8C4FFF", "<b>Amazon API Gateway</b><br>HTTP API + JWT authorizer", A, R3)
s3 = aws("simple_storage_service", "#7AA116", "<b>Amazon S3</b><br>receipts/{userId}/{id}.jpg", A, R4)

sched = aws("eventbridge", "#E7157B", "<b>EventBridge Scheduler</b><br>Mon 09:00 Australia/Sydney", Bc, R1)
api_fn = aws("lambda", "#ED7100", "<b>Lambda: expense-api</b><br>API routes, presigned uploads", Bc, R3)
proc_fn = aws("lambda", "#ED7100", "<b>Lambda: receipt-processor</b><br>parse · categorise · save", Bc, R4)

weekly_fn = aws("lambda", "#ED7100", "<b>Lambda: weekly-summary</b><br>last 7 days per user", C, R1)
ddb = aws("dynamodb", "#C925D1", "<b>Amazon DynamoDB</b><br>Expenses · Budgets tables", C, R3)
textract = aws("textract", "#01A88D", "<b>Amazon Textract</b><br>AnalyzeExpense", C, R4)

sns = aws("sns", "#E7157B", "<b>Amazon SNS</b><br>topic: expense-alerts", D, R2)
email = vertex("<b>User email inbox</b><br>budget alerts · weekly summary",
               "rounded=1;whiteSpace=wrap;html=1;dashed=1;strokeColor=#545B64;fillColor=#ffffff;fontColor=#232F3E;", D - 48, R1 - 10, 160, 60)

cw = vertex("<b>Amazon CloudWatch</b> – logs from all Lambda functions · metrics dashboard · error alarm",
            "rounded=1;whiteSpace=wrap;html=1;strokeColor=#E7157B;fillColor=#ffffff;fontColor=#232F3E;align=left;spacingLeft=60;", 290, 850, 1180, 36)
aws("cloudwatch_2", "#E7157B", "", 300, 852)  # small icon inside the bar
cells[-1] = cells[-1].replace('width="64" height="64"', 'width="32" height="32"')

# Edges – user flows (blue)
edge(user, amplify, BLUE, "1", pos=0.8, points=[(200, 502), (200, 252)], exit=(1, 0.5), entry=(0, 0.5))
edge(user, cognito, BLUE, "2", pos=0.8, points=[(200, 502), (200, 432)], exit=(1, 0.5), entry=(0, 0.5))
edge(user, apigw, BLUE, "3", pos=0.8, points=[(200, 502), (200, 612)], exit=(1, 0.5), entry=(0, 0.5))
edge(apigw, cognito, GREY, "verify JWT", dashed=True, exit=(0.5, 0), entry=(0.5, 1))
edge(apigw, api_fn, BLUE, "4", exit=(1, 0.5), entry=(0, 0.5))
edge(api_fn, ddb, BLUE, "5  read / write", exit=(1, 0.5), entry=(0, 0.5))
edge(user, s3, BLUE, "6", pos=0.8, points=[(200, 502), (200, 792)], exit=(1, 0.5), entry=(0, 0.5))

# Receipt processing (orange)
edge(s3, proc_fn, ORANGE, "7  upload event", exit=(1, 0.5), entry=(0, 0.5))
edge(proc_fn, textract, ORANGE, "8  extract", exit=(1, 0.5), entry=(0, 0.5))
edge(proc_fn, ddb, ORANGE, "9  save, check budget", points=[(700, 725), (1002, 725)], exit=(0.75, 0), entry=(0.5, 1))
edge(proc_fn, sns, ORANGE, "10  over-budget alert", points=[(682, 835), (1440, 835), (1440, 432)], exit=(0.5, 1), entry=(1, 0.5))

# Weekly summary (purple)
edge(sched, weekly_fn, PURPLE, "11", exit=(1, 0.5), entry=(0, 0.5))
edge(weekly_fn, ddb, PURPLE, "12  read expenses", exit=(0.5, 1), entry=(0.5, 0))
edge(weekly_fn, sns, PURPLE, "13  publish summary", points=[(1200, 252), (1200, 432)], exit=(1, 0.5), entry=(0, 0.5))

# SNS -> email
edge(sns, email, GREY, "14  email (filtered by userId)", exit=(0.5, 0), entry=(0.5, 1))

# Step list
steps = ("<b>Steps</b><br>1 Open web app (Amplify) · 2 Sign in (Cognito) · 3 Call API with JWT · 4 API Gateway invokes expense-api · "
         "5 Read/write DynamoDB, return presigned upload · 6 Upload receipt straight to S3 · 7 S3 event triggers receipt-processor · "
         "8 Textract reads merchant, date, total, GST · 9 Save expense, compare month total with budget · 10 Alert to SNS if over budget · "
         "11 EventBridge runs weekly-summary Monday 9am · 12 Total last 7 days · 13 Publish summary · 14 SNS emails the user")
vertex(steps, "text;html=1;whiteSpace=wrap;align=left;verticalAlign=top;fontSize=12;fontColor=#374151;", 40, 940, 1490, 70)

xml = ('<mxfile host="app.diagrams.net"><diagram id="arch" name="Architecture">'
       '<mxGraphModel dx="1600" dy="1050" grid="1" gridSize="10" guides="1" tooltips="1" connect="1" arrows="1" fold="1" '
       'page="1" pageScale="1" pageWidth="1600" pageHeight="1050" math="0" shadow="0"><root>'
       '<mxCell id="0"/><mxCell id="1" parent="0"/>' + "".join(cells) + '</root></mxGraphModel></diagram></mxfile>')

out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "images", "architecture.drawio")
with open(out, "w") as f:
    f.write(xml)
print("wrote", os.path.normpath(out))
