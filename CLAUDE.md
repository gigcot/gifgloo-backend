# Gifgloo Backend — Claude 작업 지침

## 프로젝트 개요
- GIF + 이미지 합성 서비스
- Python, FastAPI, DDD + Hexagonal Architecture

## 도메인
User, Composition, Asset, Credit, Payment, Audit

## 폴더 구조
```
{domain}/
  domain/
  application/
    ports/
      inbound/
      outbound/
        ai/
        aws/
        persistence/
        domain_bridges/
    services/
  adapter/
    inbound/fastapi/
    outbound/
      ai/
      aws/
      persistence/
      domain_bridges/
```

## 아키텍처 원칙

### 포트 입출력 타입
- **persistence 포트**: 같은 도메인의 도메인 객체 직접 사용
- **ai / aws 포트**: 포트 전용 Command / Result dataclass 정의
- **domain_bridge 포트**: 원시값(`user_id: str`) 또는 포트 전용 Command 사용 — 타 도메인 객체 직접 참조 금지

### 도메인 간 참조
- 타 도메인 참조 시 식별자(`user_id` 등)만 사용, 도메인 객체 직접 참조 금지
- 도메인 브릿지: 타 도메인의 Application Service를 주입받아 호출 — DB 모델 직접 접근 금지

### StoragePort
- 서비스는 `job_id`, `category`, `data`만 넘김
- key 생성은 어댑터 책임

### UoW
- 단일 repo만 쓸 때는 불필요
- 여러 repo를 트랜잭션으로 묶을 때 도입

## 금지 사항
- 자명한 코드에 주석 달기
- 불필요한 try/except — 조용한 실패를 만드는 방어적 코드
- `.get("key", default)`로 예외 삼키기 — 오류는 터져야 함
- 절대 None이 오지 않는 곳에 None 체크 또는 Optional 타입 힌트
- `except Exception: pass` 또는 빈 except
- 한 번만 쓸 헬퍼/유틸 함수를 미리 추상화
- 지금 요구사항에 없는 확장성 코드 추가

## 코드 컨벤션
- datetime: `datetime.now(timezone.utc)` 사용 (`utcnow()` 금지)
- UUID: `field(default_factory=lambda: str(uuid.uuid4()))`
- DTO suffix: `Command / Result` 통일 (`Request` 사용 금지)
- 예외: `shared/exceptions.py`의 커스텀 예외 사용 — 표준 `Exception` 직접 raise 금지
- 언어: 한국어로 소통, 코드 식별자는 영어 유지
