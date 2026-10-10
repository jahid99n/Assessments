# Phase 0 – Project Decisions
**ICT5205 Cloud Computing – Assignment 3**
**Project:** Smart Expense Tracker (cloud-based receipt scanning and spending analysis)

Status: DRAFT – to be confirmed with tutor. Nothing is deployed yet.

---

## 1. Tutor proposal (send or show this to your tutor)

> **Project title:** Smart Expense Tracker – a serverless cloud application for automatic receipt scanning and spending analysis
>
> **Idea:** Users sign in to a web app and upload a photo of a shopping receipt. The image is stored in Amazon S3, which automatically triggers an AWS Lambda function. The function uses Amazon Textract (AnalyzeExpense) to extract the merchant, date and total, and saves the result in Amazon DynamoDB. A dashboard shows the user's spending in tables and charts (by category and by month). If a user goes over their monthly budget, Amazon SNS sends an email alert, and a scheduled Amazon EventBridge rule emails a weekly spending summary. The front end is hosted on AWS Amplify, users sign in with Amazon Cognito, the API is exposed through Amazon API Gateway, and everything is monitored in Amazon CloudWatch.
>
> **Distributed design:** processing (Lambda + Textract) is separate from storage (S3 + DynamoDB), with an event-driven/publish–subscribe pattern (S3 upload events and SNS notifications) and a scheduled job (EventBridge).
>
> **Cloud platform:** AWS (10 services).
>
> **Questions for the tutor:**
> 1. Is this topic acceptable for Assignment 3?
> 2. Do all 10 listed services count towards the "8 cloud services" criterion?
> 3. Where can we find the reflection questions and the contribution agreement template?

---

## 2. How the project meets each requirement

| Assignment requirement | How we meet it |
|---|---|
| 1. Distributed model | Processing (Lambda, Textract) separate from storage (S3, DynamoDB) + event-driven publish/subscribe (S3 events → Lambda, SNS alerts) + scheduled job (EventBridge) |
| 2. Use of cloud services | 10 AWS services (see section 3) |
| 3. Cloud storage + cloud datastore | S3 (receipt images) + DynamoDB (expense records) |
| 4. Client-side visualization, deployed in cloud | Web dashboard with an expense table + charts (pie by category, bar by month), hosted on AWS Amplify |
| 5. Contribution agreement | Roles in section 5, form signed by all members |

**Rubric targets:** 8+ services → 8/8 · separate processing/storage + one extra distributed pattern → 3/3

---

## 3. Final service list

| # | AWS service | Purpose in our project | Rubric value |
|---|---|---|---|
| 1 | **AWS Amplify (Hosting)** | Hosts the web front end (HTML/JS dashboard) | Cloud deployment of the web app |
| 2 | **Amazon Cognito** | User sign-up/sign-in; each user sees only their own expenses | Security / identity |
| 3 | **Amazon S3** | Stores uploaded receipt images | Cloud storage (required) |
| 4 | **Amazon API Gateway** | REST API: get upload URL, list expenses, set budget, get stats | API layer / endpoints |
| 5 | **AWS Lambda** | Serverless processing: handles API calls and processes new receipts | Processing component |
| 6 | **Amazon Textract** | Reads merchant, date and total from receipt images (AnalyzeExpense) | Machine learning service |
| 7 | **Amazon DynamoDB** | Stores expense records and user budgets | Cloud datastore (required) |
| 8 | **Amazon SNS** | Email alerts when monthly budget is exceeded | Publish/subscribe, push notifications |
| 9 | **Amazon EventBridge** | Scheduled rule for weekly summary emails | Event-driven / scheduling |
| 10 | **Amazon CloudWatch** | Logs, metrics, dashboard and error alarm | Monitoring |

Two spare services above the 8 needed give a safety margin if one is not accepted.

**Design note from testing:** Australian receipts use DD/MM/YYYY dates (e.g. `04/11/2024` = 4 Nov 2024). Textract returns the raw text, so the Lambda must parse dates as day-first. Total comes from the `TOTAL` field, GST from `TAX`, merchant from `VENDOR_NAME`.

---

## 4. Technology decisions

| Item | Decision | Reason |
|---|---|---|
| Cloud platform | **AWS** | All required services available; matches tutorial sheets |
| Region | **ap-southeast-2 (Sydney)** | Closest region; Textract is available there (verify in console before building) |
| Backend language | **Python 3.12** (Lambda + boto3) | Simple, well documented, team already uses Python |
| Front end | **Plain HTML + JavaScript + Chart.js** | No framework to learn; easy to host on Amplify |
| Login on front end | **Cognito Hosted UI** | No custom login code needed |
| Infrastructure setup | **AWS Console** (manual, with screenshots) | Screenshots double as the Developer Manual; no IaC tool to learn |
| Code repository | **GitHub**, folders `code/`, `deploy/`, `images/`, `report/` | Required submission structure |
| Charts | **Chart.js** (pie: by category, bar: by month) | Meets "graphical format" requirement |

### Data design (draft)

**DynamoDB table `Expenses`**

| Attribute | Type | Example |
|---|---|---|
| `userId` (partition key) | String | Cognito user ID |
| `expenseId` (sort key) | String | `2026-10-09#a1b2c3` |
| `merchant` | String | `Woolworths` |
| `date` | String | `2026-10-09` |
| `total` | Number | `45.60` |
| `category` | String | `Groceries` |
| `imageKey` | String | `receipts/<userId>/a1b2c3.jpg` |
| `createdAt` | String | ISO timestamp |

**DynamoDB table `Budgets`**: `userId` (partition key), `monthlyLimit`, `email`

**S3 bucket:** `expense-tracker-receipts-<group-name>` with `receipts/<userId>/` prefix

**API routes (API Gateway → Lambda)**

| Method | Route | Purpose |
|---|---|---|
| POST | `/upload-url` | Returns a presigned S3 URL so the browser uploads directly to S3 |
| GET | `/expenses` | List the user's expenses |
| PUT | `/expenses/{id}` | Edit category or fix a wrongly-read value |
| DELETE | `/expenses/{id}` | Delete an expense |
| GET | `/stats` | Totals by category and by month (for charts) |
| PUT | `/budget` | Set monthly budget |

---

## 5. Team roles (fill in names)

| Member | Student no. | Main role | Tasks | Planned share |
|---|---|---|---|---|
| ______ | ______ | Cloud / backend lead | S3, Lambda, Textract, DynamoDB, API Gateway | __% |
| ______ | ______ | Front end lead | Dashboard, Chart.js, Cognito login, Amplify hosting | __% |
| ______ | ______ | Notifications & monitoring | SNS, EventBridge, CloudWatch, testing | __% |
| ______ | ______ | Documentation lead | Report, user/developer manual, slides, video | __% |

Everyone takes screenshots of their own setup steps and writes that part of the Developer Manual. Adjust rows to the group size. These shares go into the Contribution Agreement.

---

## 6. Budget and account safety

Expected cost: **close to $0** if we stay within the free tier and use a few test receipts.

| Service | Free tier (verify on AWS pricing page) |
|---|---|
| Lambda, API Gateway, DynamoDB, SNS, CloudWatch, Cognito, S3 | Covered by free tier at our usage |
| Textract AnalyzeExpense | Limited free pages for new accounts, then charged per page; **use < 50 test receipts** |
| Amplify Hosting | Free tier covers a small static site |

Rules:
1. Create an **AWS Budgets alert** before building anything (done: $15, since $7.69 of usage already existed this month).
2. Turn on **MFA for the root account**; do the work as an **IAM user**, not root.
3. Use **one shared AWS account** for the project (one member owns it), giving others IAM users.
4. Build everything in **ap-southeast-2** only.
5. **Never commit AWS keys** to GitHub.
6. After marking, **delete all resources**.

---

## 7. Phase 0 checklist

- [ ] Agree on topic in group
- [ ] Show proposal (section 1) to tutor and get approval
- [ ] Ask tutor for reflection questions and contribution form template
- [ ] Fill in team roles (section 5)
- [x] Choose the shared AWS account (Shuvo's account)
- [ ] Enable root MFA + create IAM users (postponed – do before Phase 3)
- [x] Set up AWS Budgets alert ($15 monthly cost budget, `Assignment3-Budget`) – verify email
- [x] Checked October bill: $0 actual (Free Tier credits); old EC2 + RDS running 24/7 in us-east-1 – decision: DELETE (not needed)
- [x] Textract AnalyzeExpense tested with AWS sample receipt (vendor, date, subtotal, tax, total all read correctly)
- [x] Tested Textract with our own Coles receipt: vendor, ABN, date, total ($40.00) and GST ($0.38) read correctly
- [ ] Confirm Textract page loads in Sydney region (last test ran in us-east-1)
- [ ] Create GitHub repo with `code/`, `deploy/`, `images/`, `report/` folders
- [ ] Collect 10–20 sample receipt photos for testing (own receipts, blur personal details)
- [ ] Note demo week (Week 6) and submission deadline (Sunday Week 7, 11:59pm) in calendar

When all boxes are ticked → move to **Phase 1: Design** (architecture diagram, finalise data design).
