"""크롤링 → 분석 → 저장 작업 흐름을 연결할 application service.

현재 Redis consumer가 뼈대 상태이므로, 실제 크롤러와 저장 계약이 확정된
후 이 모듈에서 처리 순서를 구현한다.
"""
