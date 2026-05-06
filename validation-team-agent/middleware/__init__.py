"""Execution-time guards and logging for the validation-team-agent harness.

실행 전후 통제 (권한 / 민감정보 / 표본 / 누수 / 산출물 완결성)와 실행 로깅을
제공한다. 미들웨어는 파일 시스템에 부작용을 가질 수 있으나, 본 모듈의 함수는
가능한 한 순수하게 작성하고 부작용은 호출자가 명시적으로 주도하도록 한다.
"""
