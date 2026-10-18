#!/usr/bin/env bash
# ==============================================================================
# Script: Push Production Release to https://github.com/ejazahmad989/ICT
# Author: Ejaz Ahmed (ejazahmad989@gmail.com)
# ==============================================================================

set -e

echo "=== Preparing ICT Release for https://github.com/ejazahmad989/ICT ==="

# Check if git is initialized
if [ ! -d ".git" ]; then
    echo "Initializing clean git repository..."
    git init
    git branch -M main
fi

# Configure release author identity
git config user.name "Ejaz Ahmed"
git config user.email "ejazahmad989@gmail.com"

# Stage all production files
echo "Staging files..."
git add .

# Create production release commit
echo "Creating release commit..."
git commit -m "feat: initial production release v1.0.0 for ERPNext v14, v15 & v16

Author: Ejaz Ahmed <ejazahmad989@gmail.com>
Co-authored-by: Rahil Ali <rahilali3311@gmail.com>" || echo "Working tree clean, proceeding to tag..."

# Create annotated release tag v1.0.0
if ! git rev-parse v1.0.0 >/dev/null 2>&1; then
    echo "Creating git release tag v1.0.0..."
    git tag -a v1.0.0 -m "Release v1.0.0: Certified for Frappe/ERPNext v14, v15 & v16"
fi

# Set remote origin to public inter_company_transactions repo
echo "Setting git remote to https://github.com/ejazahmad989/inter_company_transactions.git..."
git remote remove ict 2>/dev/null || true
git remote add origin https://github.com/ejazahmad989/inter_company_transactions.git

echo ""
echo "=============================================================================="
echo "READY TO PUSH!"
echo "Run the following command in your terminal to push your release to GitHub:"
echo ""
echo "    git push -u origin main --tags"
echo ""
echo "If GitHub prompts for credentials, use your GitHub username (ejazahmad989)"
echo "and your GitHub Personal Access Token (PAT) as the password."
echo "=============================================================================="
