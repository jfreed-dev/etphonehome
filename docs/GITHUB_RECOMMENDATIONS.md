# GitHub Repository Recommendations

This document lists recommended improvements to the GitHub repo setup for ET Phone Home. It assumes the repo is public and there is a single maintainer. Items are ordered by importance.

## High Priority

1. **Enable branch protection on `main`**
   - Require status checks to pass (build, tests, lint).
   - Prevent force pushes and deletions.
   - Optional: allow admins to bypass when necessary (single-maintainer workflow).

2. **Add CODEOWNERS**
   - Assign yourself as owner for `server/`, `client/`, `shared/`, `web/`, and `deploy/`.
   - Even with one maintainer, this helps future contributors and clarifies ownership.

3. **Security policy alignment**
   - Confirm `SECURITY.md` links are valid and point to the current reporting process.
   - Add a private disclosure contact (email or security issue intake).

4. **Dependabot scope**
   - Ensure `dependabot.yml` covers Python, npm (web), GitHub Actions, and Docker.
   - Set update cadence and grouping (e.g., weekly + grouped minor bumps).

## Medium Priority

1. **Release process**
   - Add a standard release workflow file (if not already) for tagging and publishing artifacts.
   - Ensure releases attach build artifacts and checksums.
   - Add a `CHANGELOG.md` or auto-release notes workflow.

2. **Issue templates**
   - Add templates for bugs, feature requests, and security issues.
   - Include required fields for environment, steps to reproduce, expected behavior.

3. **PR template improvements**
   - Expand `PULL_REQUEST_TEMPLATE.md` to include tests run and risk assessment.
   - Keep it lightweight to avoid slowing solo work.

4. **Contributing guidelines**
   - Ensure `CONTRIBUTING.md` includes local setup, lint/test commands, and commit expectations.

## Lower Priority

1. **Repository metadata**
   - Add GitHub Topics for discoverability (e.g., mcp, ssh, remote-access, svelte, python).
   - Add a short repo description and homepage link.

2. **CI matrix and artifacts**
   - Add Python version matrix (3.10–3.12) in CI.
   - Add Web UI build checks in CI to ensure frontend remains buildable.

3. **Security scanning**
   - Enable GitHub Advanced Security if available.
   - Add CodeQL analysis for Python and JavaScript.

4. **Automation**
   - Add a weekly scheduled workflow for housekeeping (dependency updates, security scans).
   - Add a label automation workflow (triage/labels based on files or keywords).
