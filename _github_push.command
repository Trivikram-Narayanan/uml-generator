#!/bin/bash
# UMLGen – GitHub push helper
set -e

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=== UMLGen GitHub Setup ==="
echo ""

# 1. Remove any leftover git locks / bad directories
rm -f .git/index.lock 2>/dev/null || true
python3 -c "
import shutil, os
for e in os.scandir('frontend/src'):
    if '{' in e.name:
        print('Removing:', e.name)
        shutil.rmtree(e.path, ignore_errors=True)
" 2>/dev/null || true

# 2. Remove empty subdirs
rmdir frontend/src/components/app 2>/dev/null || true
rmdir frontend/src/components/landing 2>/dev/null || true
rmdir frontend/src/components/ui 2>/dev/null || true
rmdir frontend/src/context 2>/dev/null || true

# 3. Git setup
git config user.email "trivikramnarayanan@gmail.com"
git config user.name "Trivikram Narayanan"
git branch -m main 2>/dev/null || true

git add .
git commit -m "Initial commit: UMLGen – AI-powered UML diagram and code generator" 2>/dev/null || echo "(already committed, skipping)"

# 4. Push to GitHub
GITHUB_USER=$(gh api user -q .login 2>/dev/null) || true

if [ -z "$GITHUB_USER" ]; then
  echo ""
  echo "⚠  gh CLI not authenticated. Run: gh auth login"
  echo "   Then re-run this script."
  read -p "Press Enter to close..."
  exit 1
fi

echo "GitHub user: $GITHUB_USER"

# Check if repo already exists
if gh repo view "$GITHUB_USER/uml-generator" &>/dev/null 2>&1; then
  echo "Repo already exists – pushing to existing remote..."
  git remote remove origin 2>/dev/null || true
  git remote add origin "https://github.com/$GITHUB_USER/uml-generator.git"
  git push -u origin main --force
else
  echo "Creating new public repo and pushing..."
  gh repo create uml-generator --public --source=. --remote=origin --push
fi

echo ""
echo "✓ Done! https://github.com/$GITHUB_USER/uml-generator"
echo ""
read -p "Press Enter to close..."
