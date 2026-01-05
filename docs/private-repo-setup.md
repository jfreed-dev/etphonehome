# Private Repository Setup Guide

This guide explains how to set up and use the private/public repository split for ET Phone Home.

## Quick Reference

| Component | Purpose |
|-----------|---------|
| Private repo | Development with encrypted secrets |
| Public repo | Open source release (sanitized) |
| git-crypt | Transparent file encryption |
| GitHub Actions | Automated sync to public |
| `.gitignore.public` | Files to exclude from public |
| `.gitattributes` | Files to encrypt with git-crypt |

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                     DEVELOPMENT WORKFLOW                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Developer (with GPG key)                                       │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────┐                   │
│  │         PRIVATE REPOSITORY              │                   │
│  │  github.com/you/etphonehome-private     │                   │
│  │                                         │                   │
│  │  ┌─────────────────────────────────┐   │                   │
│  │  │ Encrypted files (git-crypt):    │   │                   │
│  │  │ • .secrets/                     │   │                   │
│  │  │ • .project_settings/            │   │                   │
│  │  │ • ansible/secrets/*.yml         │   │                   │
│  │  │ • *.pem, *.key                  │   │                   │
│  │  │ • .mcp.json                     │   │                   │
│  │  └─────────────────────────────────┘   │                   │
│  │                                         │                   │
│  │  Regular files:                         │                   │
│  │  • Source code                          │                   │
│  │  • Documentation                        │                   │
│  │  • Tests                                │                   │
│  └─────────────────────────────────────────┘                   │
│       │                                                         │
│       │ Push to main                                            │
│       ▼                                                         │
│  ┌─────────────────────────────────────────┐                   │
│  │      GitHub Actions Workflow            │                   │
│  │  .github/workflows/sync-to-public.yml   │                   │
│  │                                         │                   │
│  │  1. Checkout private repo               │                   │
│  │  2. Remove files in .gitignore.public   │                   │
│  │  3. Push to public repo                 │                   │
│  └─────────────────────────────────────────┘                   │
│       │                                                         │
│       ▼                                                         │
│  ┌─────────────────────────────────────────┐                   │
│  │          PUBLIC REPOSITORY              │                   │
│  │  github.com/you/etphonehome             │                   │
│  │                                         │                   │
│  │  • Source code (sanitized)              │                   │
│  │  • Documentation                        │                   │
│  │  • No secrets or private files          │                   │
│  └─────────────────────────────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Initial Setup

### Prerequisites

- Git with git-crypt installed (`sudo apt-get install git-crypt` or `brew install git-crypt`)
- GPG key for encryption
- GitHub Personal Access Token (PAT) with `repo` scope

### Step 1: Create Repositories on GitHub

1. **Private repository**: Create `etphonehome-private` (private visibility)
2. **Public repository**: Create `etphonehome` (public visibility)

### Step 2: Initialize git-crypt (Already Done)

```bash
# This was done during setup
git-crypt init
```

This generates a symmetric key stored in `.git/git-crypt/keys/default`.

### Step 3: Add Authorized Users

Add your GPG key to allow decryption:

```bash
# List your GPG keys
gpg --list-keys

# Add your key to git-crypt
git-crypt add-gpg-user YOUR_GPG_KEY_ID
```

This creates a `.git-crypt/` directory with the encrypted key for each user.

### Step 4: Configure GitHub Secrets

In your **private** repository settings (Settings > Secrets and variables > Actions):

1. Create secret `PUBLIC_REPO_PAT`:
   - Go to GitHub Settings > Developer settings > Personal access tokens
   - Generate new token (classic) with `repo` scope
   - Copy the token and add it as a repository secret

### Step 5: Push to Private Repository

```bash
# Add private remote
git remote add private https://github.com/YOUR_USERNAME/etphonehome-private.git

# Push to private
git push private main
```

### Step 6: Initial Sync to Public

The GitHub Actions workflow will automatically sync to public on push to main.

For manual sync or force push:
1. Go to Actions tab in private repo
2. Select "Sync to Public Repo" workflow
3. Click "Run workflow"
4. Optionally enable "Force push" for initial sync

## Daily Workflow

### Working with Encrypted Files

```bash
# Check git-crypt status
git-crypt status

# See which files are encrypted
git-crypt status -e

# Unlock repository (decrypt files locally)
git-crypt unlock

# Lock repository (for testing or security)
git-crypt lock
```

### Adding New Secrets

1. Add the file pattern to `.gitattributes`:
   ```
   path/to/secret/** filter=git-crypt diff=git-crypt
   ```

2. Add the same pattern to `.gitignore.public`:
   ```
   path/to/secret/
   ```

3. Add the file and commit:
   ```bash
   git add path/to/secret/file
   git commit -m "Add encrypted secret"
   ```

### Pushing Changes

```bash
# Push to private repo (triggers sync to public)
git push private main

# Or if origin is set to private
git push origin main
```

## File Classification

### Encrypted Files (`.gitattributes`)

These files are tracked in the private repo but encrypted:

| Pattern | Description |
|---------|-------------|
| `.secrets/**` | General secrets directory |
| `.project_settings/**` | Project-specific settings |
| `.mcp.json` | MCP config (may contain API keys) |
| `ansible/secrets/*.yml` | Ansible secrets |
| `.vault_pass`, `.vault_password` | Ansible vault passwords |
| `*.pem`, `*.key` | Private keys |
| `kubeconfig`, `talosconfig` | Kubernetes/Talos configs |

### Excluded from Public (`.gitignore.public`)

These files exist in private but are removed before syncing to public:

- All encrypted files (listed above)
- IDE settings (`.idea/`, `.vscode/`)
- AI assistant context (`CLAUDE.md`, `.claude/`)
- Build artifacts and local configs

### Normal Files

Everything else is tracked normally and synced to both repos.

## Adding Team Members

To allow another developer to work with the private repo:

1. **Get their GPG public key**:
   ```bash
   # They export their key
   gpg --export --armor their@email.com > their-key.asc
   ```

2. **Import and trust their key**:
   ```bash
   gpg --import their-key.asc
   gpg --edit-key their@email.com
   # In GPG prompt: trust, 5 (ultimate), quit
   ```

3. **Add them to git-crypt**:
   ```bash
   git-crypt add-gpg-user their@email.com
   git commit -m "Add team member to git-crypt"
   git push
   ```

4. **They clone and unlock**:
   ```bash
   git clone https://github.com/you/etphonehome-private.git
   cd etphonehome-private
   git-crypt unlock
   ```

## Troubleshooting

### "Cannot decrypt" Errors

```bash
# Ensure you have the GPG key
gpg --list-secret-keys

# Try unlocking explicitly
git-crypt unlock
```

### Sync Workflow Fails

1. Check the `PUBLIC_REPO_PAT` secret is set correctly
2. Verify the PAT has `repo` scope
3. Ensure the public repo exists
4. Check Actions logs for specific errors

### File Shows as Encrypted in GitHub

This is expected! Encrypted files appear as binary data on GitHub. They decrypt automatically when you clone with git-crypt unlocked.

### Need to Re-encrypt After Leak

If a secret is leaked:

1. Rotate the compromised secret immediately
2. If the git-crypt key is compromised:
   ```bash
   # Generate new key
   git-crypt init --force

   # Re-add all users
   git-crypt add-gpg-user USER1
   git-crypt add-gpg-user USER2

   # Force push
   git push --force
   ```

## Security Best Practices

1. **Never commit then uncomment secrets** - Git history preserves all commits
2. **Use `.gitignore.public` for new secret patterns** - Add before creating the file
3. **Rotate PATs regularly** - GitHub PATs should be rotated quarterly
4. **Audit git-crypt users** - Remove users who no longer need access
5. **Keep GPG keys secure** - Use strong passphrases, store backups safely
