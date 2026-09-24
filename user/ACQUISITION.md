# 신규가입 최초 유입 저장

실험: https://app.notion.com/p/3e5920d3d9998184b562e08ddd6b0da6

## 범위와 구조

신규가입자의 최초 유입만 기존 users 테이블에 저장한다. acquisition_source, acquisition_medium, acquisition_campaign, acquisition_content는 각각 nullable VARCHAR(100)이다. 시각은 기존 created_at을 사용한다. 별도 테이블·인덱스·타 도메인 참조는 추가하지 않는다.

프론트 LoginModal → OAuth 시작 어댑터의 acquisition 입력 검증 → 기존 서명된 OAuth state와 쿠키 일치 검증 → SocialLoginCommand → SocialLoginService 신규가입 분기 → User.Acquisition 값 객체 → 기존 UserRepositoryPort → SQLAlchemy 어댑터 순서다. 동기·비동기 조회 모두 동일한 값 객체를 복원한다.

기존 계정 로그인은 유입 정보를 채우거나 갱신하지 않는다. 저장소의 기존 계정 갱신에도 유입 컬럼을 포함하지 않는다. 태그 없는 가입과 기존 사용자 데이터는 NULL이다. 유입 값은 사용자가 제공한 분석용 라벨이며 인증·무료 지급·권한 판단의 근거가 아니다. 기존 state에는 acquisition 필드가 없어도 동작한다.

## 배포 순서

1. 백업 및 대상 환경을 확인하고 202609240001 마이그레이션을 먼저 적용한다.
2. 백엔드를 배포한다. 기존 프론트 요청은 acquisition 없이도 동작한다.
3. 프론트의 OAuth 유입 전송 변경을 배포한다.

이 작업에서 운영 DB 마이그레이션·배포는 실행하지 않았다. downgrade는 수집된 유입 컬럼을 삭제하므로 데이터 보존이 필요하면 먼저 내보내야 한다.

## 검증

`python -m unittest discover -s user/unit_tests -v`

OAuth 전달·입력 길이·state 불일치 거부·신규 저장·재로그인 불변·동기/비동기 매핑·태그 없는 가입·SQLite 마이그레이션 왕복을 확인한다. PostgreSQL 운영 환경 적용과 실제 외부 소셜 로그인은 별도 배포 검증이 필요하다.
