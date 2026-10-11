# Offline full-stack harness

Run `uv sync --frozen` in the project root, `npm.cmd ci` in `code/frontend`, then
`npm.cmd run test:integration` there. Microsoft Edge is required. Playwright starts
and stops the Python server at 127.0.0.1:5181 and Vite at 127.0.0.1:5180 automatically.

Only `server.py` and the separate frontend `integration/entry.jsx` create the test
environment. Production handlers/main.jsx contain no authentication bypass. Never
package this harness, expose it on a public interface, or use personal data in it.

The browser executes real pages, `createApi`, validation and `postReceipt`. The
gateway invokes the real Python API handler with HTTP API-compatible route/claims
context. Fixed `local-alice`/`local-bob` identities model the trusted authorizer
boundary; real Cognito and JWT signature/expiry validation are not tested here.

Moto supplies in-process DynamoDB, S3 versioning and SNS. Dummy credentials are set
before clients are created, metadata lookup is disabled and botocore's actual HTTP
transport raises on any attempted network call. Textract returns explicit fixtures,
including missing fields and throttling; the real parser, categorisation, hash/lease
protection and totals code run without replacements.

Playwright redirects only the AWS upload transport to the loopback S3 simulation,
preserving the actual multipart request. All other external browser traffic is blocked.
The simulator compares submitted fields against the API's issued fields, decodes the
real signed policy and checks expiry/exact conditions/content length/file-last order.
It does not emulate AWS signature cryptography, CORS or IAM. Synthetic image signatures
are sufficient for mocked Textract; they are not real receipt/OCR evidence.

`/__test/scenario` and `/__test/replay` are loopback test controls, not application
routes. The integration Vite configuration rejects builds. The standard production
build uses only `src/main.jsx`; build checks search for demo and harness markers.
Ports, cache directory and test dependencies are isolated from the production build.

The six serial tests share one disposable in-memory backend and check all nine API
routes, user separation, CRUD totals/pagination, actual forms, JPEG/PNG uploads,
Australian dates, duplicate events/files, missing fields, transient recovery, signed
ownership/type/size tampering, the exact 5 MiB size boundary and dashboard refresh.
Results go to `report/stage4-integration.xml`. Closing the server discards all data.
