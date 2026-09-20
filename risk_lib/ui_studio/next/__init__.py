"""차세대 UI 스튜디오 (병렬 전달 경로). app.py 는 그대로 두고 옆에 선다.

`python -m risk_lib.cli ui-studio --next` 가 이 패키지를 고른다.
"""

from risk_lib.ui_studio.next.render import render_next, write_app_next

__all__ = ["render_next", "write_app_next"]
