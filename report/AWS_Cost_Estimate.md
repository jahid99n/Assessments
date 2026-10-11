# AWS cost estimate — Stage 4

Prepared 11 October 2026. **Planning estimate, not an observed bill.** No resources were deployed. Currency is USD before taxes; no unverified USD/AUD conversion is used. Budget approximately **USD 3–6 per month** for the small demonstration workload below, with a USD 10 billing alert. An alert is not a spending cap.

## Workload assumptions

Five direct Cognito users; 100 single-image receipts/month; 10,000 authenticated API requests including polling; 12,000 Lambda invocations averaging one second at 256 MB; 100,000 DynamoDB read request units and 10,000 write request units; 1 GB of receipt/version storage; 0.1 GB database storage; 100 SNS email deliveries; four/five weekly schedules; 100 Amplify standard build minutes, 1 GB CDN storage and 5 GB served; 0.1 GB CloudWatch log ingestion with 14-day retention. These are estimates, not performance measurements. Large paged expense queries or SNS audits can consume more reads/time.

| Service | Calculation / allowance | Approximate monthly USD |
|---|---|---:|
| Textract AnalyzeExpense | 100 pages × $0.01 Sydney first-tier rate | 1.00 |
| Amplify static hosting | 100 × $0.01 build minutes + 5 × $0.15 GB served + 1 × $0.023 GB stored | 1.773 |
| Lambda | 12,000 × 0.25 GB × 1 s × $0.0000166667, plus request allowance | 0.053 |
| DynamoDB on-demand | 100,000 × $0.0000001425 + 10,000 × $0.0000007100; small storage allowance | 0.05 |
| S3 | 1 GB × $0.025, plus small request/transfer allowance | 0.06 |
| HTTP API Gateway | 10,000 requests; conservative allowance pending account calculator | 0.02 |
| Cognito Essentials | Five direct users within published 10,000-MAU allowance, if available to this account/organisation | 0.00 |
| SNS | 100 email deliveries plus API requests; conservative allowance | 0.03 |
| EventBridge Scheduler | Four/five invocations; conservative allowance | <0.01 |
| CloudWatch | Four standard alarms × $0.10 + one emitted custom metric × $0.30 + logs allowance | 0.80 |
| **Illustrative total** | Rounded; allowances intentionally exceed some tiny request charges | **about 3.80** |

The range allows for retries, setup builds and modest variation. Except for Cognito's stated allowance, the estimate does not subtract free tiers or promotional credits. Shared account usage can exhaust allowances. The custom metric is billed when emitted; actual CloudWatch charges may be lower. No paid dashboard, dedicated KMS key, WAF, NAT Gateway, EC2, load balancer or RDS is provisioned by the template. Cognito default email delivery has demonstration-scale quotas; custom SES/SMS configurations and their charges are outside this template.

## Rate evidence and limitations

The public AWS Sydney price-list JSON was read locally without AWS credentials. At inspection, Textract's publication date was 2026-09-11: `APS2-SyncExpensePagesProcessed` first tier $0.0100000000/page. Other inspected Sydney catalogues reported S3 standard storage $0.025/GB-month; DynamoDB standard reads $0.0000001425/unit and writes $0.0000007100/unit; Lambda x86 duration $0.0000166667/GB-second; CloudWatch standard alarms $0.10 and first-tier custom metrics $0.30. These are published unit prices, not measured workload costs.

- [Sydney Textract public price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonTextract/current/ap-southeast-2/index.json) and [Textract pricing](https://aws.amazon.com/textract/pricing/).
- [Amplify pricing](https://aws.amazon.com/amplify/pricing/) supports the build/storage/transfer calculation above.
- [Sydney Lambda price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AWSLambda/current/ap-southeast-2/index.json) and [Lambda pricing](https://aws.amazon.com/lambda/pricing/).
- [Sydney DynamoDB price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonDynamoDB/current/ap-southeast-2/index.json) and [DynamoDB pricing](https://aws.amazon.com/dynamodb/pricing/).
- [Sydney S3 price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonS3/current/ap-southeast-2/index.json), [S3 pricing](https://aws.amazon.com/s3/pricing/), [API Gateway pricing](https://aws.amazon.com/api-gateway/pricing/).
- [Cognito pricing](https://aws.amazon.com/cognito/pricing/), [SNS pricing](https://aws.amazon.com/sns/pricing/), [EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/).
- [Sydney CloudWatch price list](https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonCloudWatch/current/ap-southeast-2/index.json) and [CloudWatch pricing](https://aws.amazon.com/cloudwatch/pricing/).

Recreate the estimate in AWS Pricing Calculator in Sydney immediately before deployment. A receipt page costs about one cent under the inspected rate: 1,000 pages add approximately $10 of Textract expense before eligible credits. Object versioning charges for every stored version; lifecycle retention is 365 days, not immediate deletion. Retained tables, Cognito users and the versioned bucket survive stack deletion and can continue incurring charges. SAM deployment artifacts and Amplify hosting must also be cleaned up. Public sign-up, repeated uploads and overly frequent polling can increase costs; API throttling is not a per-user spending limit.
