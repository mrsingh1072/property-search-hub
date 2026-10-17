# Publish later to your GitHub

No push is needed now. Finish local setup and testing first.
Suggested repository name: `apnaghar-ai`.

When you decide to publish, create an empty repository under your own account.
Keep the original contributor credit in `NOTICE.md`. Agree on licensing with the
project's collaborators before adding a license for the original code.

From the project directory, inspect the files before committing:

```powershell
git init
git branch -M main
git add .
git status --short
git diff --cached --stat
```

Check that `.env`, `.venv`, `runtime/`, calendar tokens and service-account files
are excluded. Review sample data and historical screenshots for contact details
and rights before publishing. `.gitignore` is a safeguard, not a content review.

Only when ready:

```powershell
git commit -m "Prepare ApnaGhar AI property assistant"
git remote add origin https://github.com/YOUR_USERNAME/apnaghar-ai.git
git push -u origin main
```

Replace `YOUR_USERNAME` with your own account. Do not put a GitHub token in the
remote URL. Authenticate using Git Credential Manager or your usual GitHub tool.
