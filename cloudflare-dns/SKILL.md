---
name: cloudflare-dns
description: Use the flarectl command-line tool to manage Cloudflare DNS records, including listing, adding, updating, and deleting DNS records, as well as querying zone information. This skill must be triggered whenever a user mentions "Cloudflare DNS," "CF DNS," "add DNS record," "delete DNS record," "update DNS," "view DNS records," "cloudflare-dns," "flarectl," or any scenario involving Cloudflare DNS management.
---

# Cloudflare DNS Management

## Environment Setup

### Install flarectl

In the current environment (Alpine Linux arm64), the preinstalled version can be used directly. If it is not available, install it from the release:

```bash
if ! which flarectl > /dev/null 2>&1; then
  wget -q https://github.com/wsvn53/flarectl/releases/download/flarectl-v0.1.0-alpine-arm64/flarectl-linux-arm64 \
    -O /usr/local/bin/flarectl && chmod +x /usr/local/bin/flarectl
fi
```

### Authentication Configuration

flarectl supports two authentication methods. Prefer the API Token method:

**Method 1: API Token (recommended)**
```bash
export CF_API_TOKEN=<your_token>
```

**Method 2: Global API Key**
```bash
export CF_API_KEY=<your_key>
export CF_API_EMAIL=<your_email>
```

Optional:
```bash
export CF_ACCOUNT_ID=<account_id>   # Specify when using multiple accounts
```

Check whether the environment variables are set:
```bash
[ -n "$CF_API_TOKEN" ] && echo "Token: set" || echo "Token: NOT SET"
[ -n "$CF_API_KEY" ] && echo "API Key: set" || echo "API Key: NOT SET"
```

If they are not set, tell the user which variable names are required and provide setup links:
- API Token: [Set CF_API_TOKEN](minis://settings/environments?create_key=CF_API_TOKEN&create_value=)
- API Key: [Set CF_API_KEY](minis://settings/environments?create_key=CF_API_KEY&create_value=) and [Set CF_API_EMAIL](minis://settings/environments?create_key=CF_API_EMAIL&create_value=)

---

## Common Operations

### Query the Zone List

```bash
flarectl zone list
```

Example output:
```
ID                               NAME          PLAN   STATUS
abc123...                        example.com   Free   active
```

### List DNS Records

```bash
# List all records for a domain
flarectl dns list --zone example.com

# Filter by type
flarectl dns list --zone example.com --type A

# Filter by name
flarectl dns list --zone example.com --name sub.example.com

# Output in JSON format (useful for parsing IDs)
flarectl --json dns list --zone example.com
```

### Add DNS Records

```bash
# A record
flarectl dns create --zone example.com --type A --name sub.example.com --content 1.2.3.4 --ttl 1

# CNAME record (enable orange-cloud proxy)
flarectl dns create --zone example.com --type CNAME --name www.example.com --content example.com --proxy

# MX record
flarectl dns create --zone example.com --type MX --name example.com --content mail.example.com --priority 10

# TXT record
flarectl dns create --zone example.com --type TXT --name _dmarc.example.com --content "v=DMARC1; p=none"

# AAAA record (IPv6)
flarectl dns create --zone example.com --type AAAA --name ipv6.example.com --content "2001:db8::1"
```

Parameter descriptions:
- `--ttl 1`: Automatic TTL (recommended); other values are in seconds (for example, `--ttl 300`)
- `--proxy`: Enable the Cloudflare orange-cloud proxy (supported only for A/AAAA/CNAME records)

### Update DNS Records

Updating requires the record `id`. Use `dns list` to get it first:

```bash
# Get the record ID
flarectl --json dns list --zone example.com --name sub.example.com | python3 -c "
import sys,json
for r in json.load(sys.stdin):
    print(r['id'], r['type'], r['name'], r['content'])
"

# Update the content
flarectl dns update --zone example.com --id <record_id> --content 5.6.7.8

# Update and enable proxy
flarectl dns update --zone example.com --id <record_id> --content 5.6.7.8 --proxy
```

### Create or Update (upsert)

```bash
# Update if it exists; create it if it does not exist
flarectl dns create-or-update --zone example.com --type A --name sub.example.com --content 1.2.3.4
```

### Delete DNS Records

```bash
# Look up the ID first
flarectl --json dns list --zone example.com --name sub.example.com | python3 -c "
import sys,json
for r in json.load(sys.stdin):
    print(r['id'], r['name'], r['type'])
"

# Delete
flarectl dns delete --zone example.com --id <record_id>
```

### Batch Delete Records with the Same Name

```bash
flarectl --json dns list --zone example.com --name sub.example.com | python3 -c "
import sys,json,subprocess
for r in json.load(sys.stdin):
    subprocess.run(['flarectl','dns','delete','--zone','example.com','--id',r['id']])
    print('Deleted:', r['id'], r['type'], r['content'])
"
```

---

## Workflow

1. **Verify authentication**: Check whether `CF_API_TOKEN` or `CF_API_KEY`+`CF_API_EMAIL` is set
2. **Confirm the domain**: If the user has not specified a zone, first use `flarectl zone list` to list available domains for the user to choose from
3. **Perform the operation**: Run list/create/update/delete as needed
4. **Display results**: After the operation, use `flarectl dns list --zone <zone>` to show the latest record status

## Notes

- Deletions are irreversible; confirm with the user before proceeding
- `--proxy` supports only A, AAAA, and CNAME record types
- MX records must specify `--priority`
- TXT record content that contains spaces must be enclosed in quotes
- The global flag `flarectl --json` must be placed before the subcommand.
