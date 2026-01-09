# ET Phone Home - File Exchange Skill

This skill manages file transfers between the MCP server and ET Phone Home clients using Cloudflare R2 as an intermediary storage layer.

## When to Use Which Tool

| Scenario | Tool | Why |
|----------|------|-----|
| Direct transfer, client online | `upload_file` / `download_file` | SFTP streaming, no size limit |
| Very large files (> 100MB) | R2 exchange (this skill) | Resumable, reliable |
| Client offline | R2 exchange (this skill) | Async transfer |
| Multiple recipients | R2 exchange (this skill) | Share URL |
| Audit trail needed | R2 exchange (this skill) | Lifecycle management |

**For most transfers, use `upload_file` / `download_file`** - they use SFTP with automatic JSON-RPC fallback.

## When to Use This Skill

Use this skill when you need to:
- Transfer files from the server to a client (especially when direct connection is complex)
- Transfer very large files (> 100MB) that benefit from resumable downloads
- Transfer files asynchronously (client doesn't need to be online immediately)
- Share files with multiple clients
- Transfer files with audit trail and lifecycle management

## How It Works

1. **Upload**: Files are uploaded to Cloudflare R2 storage with metadata
2. **Share**: Presigned URLs are generated for secure, time-limited access
3. **Download**: Recipients download files via presigned URLs
4. **Cleanup**: R2 lifecycle policies automatically delete files after 48 hours

## Configuration

The server must have R2 credentials configured via environment variables:

```bash
export ETPHONEHOME_R2_ACCOUNT_ID="your-account-id"
export ETPHONEHOME_R2_ACCESS_KEY="your-access-key"
export ETPHONEHOME_R2_SECRET_KEY="your-secret-key"  # pragma: allowlist secret
export ETPHONEHOME_R2_BUCKET="etphonehome-transfers"
```

## MCP Tools

### exchange_upload

Upload a file to R2 for transfer to a client.

**Parameters:**
- `local_path` (required): Path to file on the MCP server
- `dest_client` (optional): Destination client UUID
- `expires_hours` (optional): URL expiration in hours (default: 12, max: 12)

**Returns:**
- `transfer_id`: Unique transfer identifier
- `download_url`: Presigned URL for downloading
- `expires_at`: When the URL expires (ISO timestamp)
- `size`: File size in bytes
- `filename`: Original filename

**Example:**
```python
result = await exchange_upload(
    local_path="/tmp/deploy.tar.gz",
    dest_client="abc-123-def",
    expires_hours=6
)
# Returns: {
#   "transfer_id": "abc-123-def_20260108_143022_deploy.tar.gz",
#   "download_url": "https://...",
#   "expires_at": "2026-01-08T20:30:22Z",
#   "size": 15728640,
#   "filename": "deploy.tar.gz"
# }
```

### exchange_download

Download a file from a presigned URL to the MCP server.

**Parameters:**
- `download_url` (required): Presigned URL from exchange_upload
- `local_path` (required): Destination path on MCP server

**Returns:**
- `local_path`: Where the file was saved
- `size`: Downloaded file size in bytes

**Example:**
```python
result = await exchange_download(
    download_url="https://account.r2.cloudflarestorage.com/...",
    local_path="/tmp/received_file.tar.gz"
)
```

### exchange_list

List pending file transfers.

**Parameters:**
- `client_id` (optional): Filter by source client UUID

**Returns:**
- List of transfer objects with:
  - `key`: R2 object key
  - `size`: File size
  - `last_modified`: Upload timestamp
  - `metadata`: Transfer metadata (source_client, dest_client, filename, etc.)

**Example:**
```python
transfers = await exchange_list(client_id="abc-123-def")
# Returns: [
#   {
#     "key": "transfers/abc-123-def/abc-123-def_20260108_143022_deploy.tar.gz",
#     "size": 15728640,
#     "last_modified": "2026-01-08T14:30:22Z",
#     "metadata": {
#       "source_client": "abc-123-def",
#       "dest_client": "xyz-789-ghi",
#       "filename": "deploy.tar.gz",
#       "uploaded_at": "2026-01-08T14:30:22Z"
#     }
#   }
# ]
```

### exchange_delete

Manually delete a transfer before automatic expiration.

**Parameters:**
- `transfer_id` (required): Transfer ID from exchange_upload
- `source_client` (required): Source client UUID

**Returns:**
- `key`: R2 object key that was deleted
- `deleted`: True if successful

**Example:**
```python
result = await exchange_delete(
    transfer_id="abc-123-def_20260108_143022_deploy.tar.gz",
    source_client="abc-123-def"
)
```

## Usage Patterns

### Pattern 1: Server to Client Transfer

```python
# 1. Upload file from server
transfer = await exchange_upload(
    local_path="/path/to/config.yaml",
    dest_client="client-uuid",
    expires_hours=12
)

# 2. Share download URL with client (via command or message)
await run_command(
    client_id="client-uuid",
    cmd=f"curl -o /tmp/config.yaml '{transfer['download_url']}'"
)

# 3. Or tell user to download on client
print(f"Download URL (expires {transfer['expires_at']}): {transfer['download_url']}")
```

### Pattern 2: Client to Server Transfer

```python
# 1. Client uploads to R2 (using curl or similar)
# Client runs: curl --upload-file /path/to/logs.tar.gz "$(presigned_put_url)"

# 2. Server lists pending transfers from that client
transfers = await exchange_list(client_id="client-uuid")

# 3. Server downloads the transfer
for transfer in transfers:
    if "logs.tar.gz" in transfer["metadata"]["filename"]:
        await exchange_download(
            download_url=generate_url_from_key(transfer["key"]),
            local_path="/tmp/client_logs.tar.gz"
        )
```

### Pattern 3: Large File Transfer with Progress

```python
# For very large files, R2 provides better reliability
transfer = await exchange_upload(
    local_path="/large/database_dump.sql.gz",  # 5GB file
    dest_client="prod-server",
    expires_hours=12
)

# Client can resume downloads if interrupted
print(f"Download command: curl -L -C - -o database_dump.sql.gz '{transfer['download_url']}'")
```

## Best Practices

1. **Set appropriate expiration**: Use shorter times (1-6 hours) for sensitive files
2. **Clean up after downloads**: Use exchange_delete after successful transfer
3. **Include metadata**: Always specify dest_client for audit trail
4. **Check file size**: Files > 100MB should use R2, smaller files can use direct transfer
5. **Monitor transfers**: Regularly check exchange_list for stuck transfers

## Troubleshooting

### R2 Not Configured

```
Error: R2 not configured (missing environment variables)
```

**Solution**: Set R2 environment variables in server.env file.

### URL Expired

```
Error: 403 Forbidden - Access Denied
```

**Solution**: Presigned URL has expired. Generate a new one with exchange_list + generate new URL.

### Upload Failed

```
Error: NoCredentialsError or ClientError
```

**Solution**: Verify R2 credentials and bucket name. Test with AWS CLI: `aws s3 ls --endpoint-url https://...`

## Limitations

- Maximum URL expiration: 12 hours (for security)
- Files auto-delete after 48 hours (via R2 lifecycle policy)
- R2 free tier: 10GB storage, 1M Class A ops, 10M Class B ops per month
- Requires internet connectivity on both server and client

## Security Considerations

- Presigned URLs are time-limited and cannot be extended
- URLs can be used by anyone who has them (share securely)
- Files are encrypted at rest in R2
- Files are encrypted in transit (HTTPS)
- Consider encrypting sensitive files before upload
- R2 access logs can track who downloaded what

## Cost Estimates

With Cloudflare R2:
- Storage: $0.015/GB/month
- Class A (uploads): $4.50/million
- Class B (downloads): $0.36/million
- Egress: $0 (free!)

Typical development usage (~100 transfers/day, 5MB avg):
- ~$0.02/month (well within free tier)

Heavy usage (~1000 transfers/day, 50MB avg):
- ~$0.20/month

## See Also

- R2 setup guide: `/home/etphonehome/etphonehome/FILE_TRANSFER_IMPROVEMENT_RESEARCH.md`
- R2 dashboard: https://dash.cloudflare.com/r2
- Direct transfer tools: `upload_file`, `download_file` (for small files when both online)
