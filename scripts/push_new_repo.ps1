param(
  [Parameter(Mandatory=$true)]
  [string]$RepoUrl
)

# Run from the repository root after creating an empty GitHub repo.
# Example:
# .\scripts\push_new_repo.ps1 -RepoUrl "https://github.com/hauomu/aok-replay-lab.git"

git init
git add .
git commit -m "Initial AoK replay lab scaffold"
git branch -M main
git remote add origin $RepoUrl
git push -u origin main
