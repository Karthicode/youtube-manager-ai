#!/bin/bash
# PostToolUse hook: Auto-format files after Edit/Write operations
# Receives JSON on stdin with tool_input.file_path

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tool_input',{}).get('file_path',''))" 2>/dev/null)

if [ -z "$FILE_PATH" ] || [ ! -f "$FILE_PATH" ]; then
  exit 0
fi

EXT="${FILE_PATH##*.}"
PROJECT_ROOT="/Users/karthikananthnarayan/MyProjects/youtube-manager-ai"

case "$EXT" in
  py)
    # Python: format with black, lint-fix with ruff
    cd "$PROJECT_ROOT/backend"
    black --quiet "$FILE_PATH" 2>/dev/null
    ruff check --fix --quiet "$FILE_PATH" 2>/dev/null
    ;;
  ts|tsx|js|jsx)
    # TypeScript/JavaScript: format + lint with biome
    cd "$PROJECT_ROOT/frontend"
    npx biome check --write "$FILE_PATH" 2>/dev/null
    ;;
esac

exit 0
