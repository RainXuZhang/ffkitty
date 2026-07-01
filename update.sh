#!/bin/bash

# Define the target directory name and the repository URL
TARGET_DIR="ffkitty"
REPO_URL="https://github.com"

echo "Checking for software updates..."

# Check if the folder already exists
if [ -d "$TARGET_DIR" ]; then
    echo "Updating existing installation..."
    cd "$TARGET_DIR" || exit 1
    
    # Reset any local changes to avoid merge conflicts, then pull
    git fetch origin
    git reset --hard origin/main
    git pull origin main
else
    echo "Performing fresh installation..."
    git clone "$REPO_URL" "$TARGET_DIR"
fi

echo "Update complete!"
