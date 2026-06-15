# Scientific Team Agent

## 조사 결과 (GitHub)
- 저장소: `K-Dense-AI/scientific-agent-skills`
- 링크: https://github.com/K-Dense-AI/scientific-agent-skills
- 용도: 과학/연구 워크플로우용 Agent Skills 모음(생명정보학, 화학정보학, 시계열, 지리공간, 문헌조사 등)
- 구조: `scientific-skills/` 디렉터리 아래 개별 `SKILL.md` 기반 스킬 팩 구성

## 팀 에이전트 상속 구성
이 저장소에는 아래 팀 에이전트 프로필을 생성했습니다.

- `team_agents/scientific-team-agent.json`
  - `inherits: ["scientific-agent-skills"]`
  - `skills_path: .skills/scientific-agent-skills/scientific-skills`
  - `upstream_repo`에 원본 GitHub URL 기록

## 설치/갱신
```bash
./scripts/setup_scientific_team_agent.sh
```

네트워크가 허용되면 스킬 저장소를 `.skills/scientific-agent-skills`로 clone/pull 하고,
항상 팀 에이전트 JSON 프로필을 생성/갱신합니다.
