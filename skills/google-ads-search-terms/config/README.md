# Google Ads Search Terms config

This directory contains examples only. Prefer the project-level Google Ads
configuration verified by `seos-cli config check`.

For standalone script debugging only, create a local uncommitted `.env`:

```bash
cp config/.env.example config/.env
```

2. Fill required values:

- `GOOGLE_ADS_DEVELOPER_TOKEN`
- `GOOGLE_ADS_CLIENT_ID`
- `GOOGLE_ADS_CLIENT_SECRET`
- `GOOGLE_ADS_REFRESH_TOKEN`
- `GOOGLE_ADS_CUSTOMER_ID`

3. Optional values:

- `GOOGLE_ADS_LOGIN_CUSTOMER_ID` for MCC routing.
- `GOOGLE_ADS_API_VERSION` (default `v22`).

4. Validate:

```bash
bash scripts/auth_check.sh
```

## Notes

- Auth refresh uses `https://oauth2.googleapis.com/token`.
- Data source is Google Ads `search_term_view` (ad account queries), not organic Google SERP.
