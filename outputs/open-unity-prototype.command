#!/bin/zsh
PROJECT="/Users/vjayyi/WeChatProjects/mygame/unity/ProbabilityEdge"
EDITOR="/Applications/Unity/Hub/Editor/2022.3.62f3c1/Unity.app"
if [[ -d "$EDITOR" ]]; then
  open -a "$EDITOR" --args -projectPath "$PROJECT"
else
  open "/Users/vjayyi/Applications/Unity Hub 3.22.3.app"
fi
