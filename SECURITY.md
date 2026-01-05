# Security Policy

## Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 0.1.x   | :white_check_mark: |

## Reporting a Vulnerability

We take security seriously. If you discover a security vulnerability, please report it responsibly.

### How to Report

1. **Do NOT open a public issue** for security vulnerabilities
2. Email security concerns to: **security@freed.dev**
3. Or use GitHub's private vulnerability reporting:
   - Go to the repository's **Security** tab
   - Click **Report a vulnerability**
   - Provide details of the vulnerability

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Initial response**: Within 48 hours
- **Status update**: Within 7 days
- **Fix timeline**: Depends on severity (critical: ASAP, high: 30 days, medium: 90 days)

### What to Expect

1. Acknowledgment of your report
2. Assessment of the vulnerability
3. Development of a fix
4. Coordinated disclosure (if applicable)
5. Credit in release notes (unless you prefer anonymity)

## Security Best Practices for Users

### Client Security

- Store SSH keys securely (`~/.etphonehome/id_ed25519`)
- Use `allowed_paths` to restrict file system access
- Run the client as a non-root user when possible
- Keep the client updated to receive security patches

### Server Security

- Use a dedicated `etphonehome` user for client connections
- Configure SSH to only allow key-based authentication
- Use port 443 (HTTPS port) to pass through firewalls securely
- Enable API key authentication for HTTP transport mode
- Regularly rotate API keys

### Network Security

- All client-server communication is encrypted via SSH tunnels
- Reverse tunnels bind to localhost only
- Consider using a firewall to restrict access to the SSH port

## Known Security Considerations

1. **SSH Key Management**: Client keys are stored locally. Protect the private key file.
2. **Command Execution**: Commands run with the client user's privileges. Use `allowed_paths` to limit scope.
3. **File Transfers**: Limited to 10MB by default. Large transfers should use dedicated tools.

## Security Updates

Security updates are released as patch versions (e.g., 0.1.1, 0.1.2). Subscribe to releases to be notified:

1. Go to the repository
2. Click **Watch** > **Custom** > **Releases**
