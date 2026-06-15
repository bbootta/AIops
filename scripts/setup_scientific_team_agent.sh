#!/usr/bin/env bash
set -euo pipefail

REPO_URL="https://github.com/K-Dense-AI/scientific-agent-skills.git"
SKILL_DIR=".skills/scientific-agent-skills"
AGENT_CONFIG="team_agents/scientific-team-agent.json"

mkdir -p "$(dirname "$SKILL_DIR")" "$(dirname "$AGENT_CONFIG")"

if [ ! -d "$SKILL_DIR/.git" ]; then
  if git clone "$REPO_URL" "$SKILL_DIR"; then
    echo "Cloned scientific-agent-skills"
  else
    echo "Warning: could not clone $REPO_URL. Continuing with config generation." >&2
  fi
elif [ -d "$SKILL_DIR/.git" ]; then
  git -C "$SKILL_DIR" pull --ff-only || echo "Warning: could not update local skills repository." >&2
fi

cat > "$AGENT_CONFIG" <<JSON
{
  "name": "scientific-team-agent",
  "inherits": ["scientific-agent-skills"],
  "skills_path": "$SKILL_DIR/scientific-skills",
  "upstream_repo": "$REPO_URL",
  "description": "Team agent profile inheriting K-Dense scientific-agent-skills for research workflows."
}
JSON

echo "Created $AGENT_CONFIG"
