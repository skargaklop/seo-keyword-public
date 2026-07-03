# Google Ads Keyword Planner config

This directory contains examples only. Prefer the project-level Google Ads
configuration verified by `seos-cli config check`.

For standalone script debugging only, copy config locally:

```bash
cp config/.env.example config/.env
```

Fill required credentials:

- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_CUSTOMER_ID`

For MCC routing set `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.

Check access:

```bash
bash scripts/health_check.sh
```

## OAuth refresh token

Use standard Google OAuth flow for installed/web app. Keep refresh tokens in project-level configuration or a local uncommitted `.env`; never store real credentials in the copied skill package.
Token exchange is handled automatically in `scripts/common.sh` via:
`https://oauth2.googleapis.com/token`.

## Troubleshooting

- `PERMISSION_DENIED`: verify developer token and account access.
- `CUSTOMER_NOT_ENABLED`: check `GOOGLE_ADS_CUSTOMER_ID`.
- MCC errors: set `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.
- Version issues: set `GOOGLE_ADS_API_VERSION` (default `v22`).
