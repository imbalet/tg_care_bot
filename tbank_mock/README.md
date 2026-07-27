# T-Bank mock

Local T-Bank Internet Acquiring `/v2` mock with a hosted card form,
one-stage payments, SQLite persistence, and signed webhooks.

The supported payment lifecycle is `Init -> PaymentURL -> CONFIRMED`.
`Confirm` and `PayType` are intentionally unsupported. `Init` requires
`DATA.OperationInitiatorType=0` and validates the receipt total.

Run locally with:

```bash
uv run uvicorn tbank_mock.app:app --reload
```
