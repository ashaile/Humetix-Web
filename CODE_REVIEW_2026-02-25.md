# 코드 리뷰 결과 (2026-02-25)

**대상 커밋:** d96ed4f ~ 2b777a2 (최근 5개)
**대상 파일:** `admin_contract_create.html`, `admin_contracts.html`, `contract_sign.html`
**최종 업데이트:** 2026-02-26

---

## 1) 치명적 (즉시 수정) — 3건 전부 수정 완료

### 1-1. `admin_contract_create.html` — onclick 인라인 핸들러 XSS ✅
- **증상:** `role.key`에 작은따옴표 포함 시 JavaScript 인젝션 가능
- **수정:** `escJsStr()` 함수 추가, `rk`와 `f.type`을 escape 처리
- **완료:** 커밋 `6d991b8` (2026-02-25)

### 1-2. `admin_contracts.html` — onclick에서 title의 불완전한 escape ✅
- **증상:** 계약명에 `\` 또는 줄바꿈 포함 시 JS 문자열 탈출 가능
- **수정:** Jinja2 `tojson` 필터 적용 + onclick 속성을 홑따옴표로 변경
- **완료:** 커밋 `6d991b8`, 핫픽스 `e278259` (2026-02-25)

### 1-3. `contract_sign.html` — 서명 확인 모달에 명시적 동의 절차 없음 ✅
- **증상:** 법적 동의 항목이 정적 아이콘으로만 표시, 체크박스 없이 바로 서명 완료 가능
- **수정:** 실제 `<input type="checkbox">` 3개로 교체, 전체 동의 시 버튼 활성화, `doSubmitSign()`에서 방어 검증
- **완료:** 커밋 `6d991b8` (2026-02-25)

---

## 2) 위험 — 5건 전부 수정 완료

### 2-1. `admin_contract_create.html` — `submitContract()` HTTP 상태 미확인 ✅
- **증상:** 서버 500/400 응답 시 `res.json()` 파싱 실패로 uncaught exception
- **수정:** `if (!res.ok)` 체크 후 에러 메시지 설정 + `continue`로 다음 건 처리
- **완료:** 커밋 `2c7c687` (2026-02-26)

### 2-2. `admin_contract_create.html` — 이중 클릭으로 중복 계약 생성 ✅
- **증상:** 유효성 검증 구간에서 이중 진입 가능
- **수정:** `_submitLock` 플래그 가드로 함수 진입 자체를 차단
- **완료:** 커밋 `2c7c687` (2026-02-26)

### 2-3. `admin_contract_create.html` — `collectPreSignValues()` parseInt 미검증 ✅
- **증상:** `item.dataset.fieldIdx`가 비정상이면 NaN이 서버로 전송
- **수정:** `parseInt(..., 10)` radix 명시 + `if (isNaN(idx)) return;`
- **완료:** 커밋 `2c7c687` (2026-02-26)

### 2-4. `contract_sign.html` — `doSubmitSign()` 타임아웃 없음 ✅
- **증상:** 네트워크 지연 시 무한 대기
- **수정:** `AbortController` + 30초 타임아웃, `res.ok` 확인, 타임아웃 시 별도 메시지
- **완료:** 커밋 `2c7c687` (2026-02-26)

### 2-5. `admin_contract_create.html` — 두 번째 역할 미리서명 값이 루프 내 반복 수집 ✅
- **증상:** `collectPreSignValues(secondaryRole.key)`가 루프 안에서 매번 같은 결과 반환
- **수정:** 루프 밖에서 1회만 수집하여 공통 적용 (성능 개선)
- **완료:** 커밋 `2c7c687` (2026-02-26)

---

## 3) 개선 권장 — 5건 중 3건 수정, 2건 보류

### 3-1. `admin_contracts.html` — 날짜 정렬이 문자열 비교 ✅
- **수정:** `localeCompare` → `new Date().getTime()` 숫자 비교로 변경
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### 3-2. `contract_sign.html` — 인라인 스타일 과다 ✅
- **수정:** 확인 모달 12개 인라인 스타일 → `.confirm-variant`, `.confirm-checks`, `.confirm-actions` CSS 클래스로 분리
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### 3-3. `contract_sign.html` — 접근성(a11y) 부족 ⏸️ 보류
- `role="dialog"`, `aria-modal="true"`, `aria-label` 미적용
- 현재 사용자 대부분 스크린 리더 미사용, 추후 웹접근성 인증 필요 시 대응 예정

### 3-4. `admin_contract_create.html` — `ROLE_COLORS`가 `currentTemplate` 전에 선언 ✅
- **수정:** `currentTemplate` 등 상태 변수를 먼저 선언, `ROLE_COLORS`와 `getRoleColor()`를 그 뒤에 배치
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### 3-5. 배포 리스크 ✅ 해당없음
- DB 마이그레이션/환경변수 변경 불필요, 서버 재시작으로 배포 완료

---

## 요약

| 등급 | 건수 | 수정 | 상태 |
|------|------|------|------|
| 치명적 | 3건 | 3건 | ✅ 전부 완료 |
| 위험 | 5건 | 5건 | ✅ 전부 완료 |
| 개선 | 5건 | 3건 | 1건 보류 (a11y), 1건 해당없음 |

---
---

# UI/UX 리뷰 결과 (2026-02-25)

**대상:** 최근 변경된 3개 화면 (`contract_sign.html`, `admin_contract_create.html`, `admin_contracts.html`)
**최종 업데이트:** 2026-02-26

---

## contract_sign.html — 서명 페이지

### P0. 가짜 동의 체크마크 → 실제 체크박스로 (사용성/법적) ✅
- **수정:** 정적 ✓ → 실제 `<input type="checkbox">` 3개, 전체 동의 시 버튼 활성화
- **완료:** 커밋 `6d991b8` (2026-02-25)

### P1. 모달 버튼 순서 반전 (일관성) ✅
- **수정:** 취소를 위, 서명 완료를 아래(엄지 가까운 쪽)로 배치
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P1. 모달 인라인 스타일로 디자인 시스템 무시 (일관성) ✅
- **수정:** 12개 인라인 스타일 제거, `.modal-card.confirm-variant` 수정자 클래스로 CSS 관리
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P3. 다운로드 버튼 인라인 스타일 (유지보수) ✅
- **수정:** 14줄 인라인 스타일 → `.download-btn` CSS 클래스 + hover 효과 추가
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P3. 줌 리셋 버튼 크기 불일치 (일관성) ✅
- **수정:** `font-size:12px` 인라인 제거, 다른 줌 버튼과 동일 16px 통일
- **완료:** 커밋 `d85e4a0` (2026-02-26)

---

## admin_contract_create.html — 계약 생성

### P1. 두 번째 역할 role-dot 색상 하드코딩 (일관성) ✅
- **수정:** 하드코딩 `#ef4444` → `getRoleColor(role.key).border` 동적 색상 적용
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P2. 모바일에서 PDF가 참여자 입력보다 먼저 노출 (모바일) ⏸️ 보류
- 관리자 페이지 특성상 PC 사용이 주, 추후 모바일 최적화 시 대응 예정

### P2. 미리서명 "서명/도장" 버튼 터치 영역 부족 (접근성) ✅
- **수정:** `padding: 6px 12px` → `padding: 8px 16px; min-height: 36px; font-size: 13px`
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P3. 참여자 카드 label-input 연결 누락 (접근성) ✅
- **수정:** 이름/연락처 4곳에 `<label for="...">` 속성 추가
- **완료:** 커밋 `d85e4a0` (2026-02-26)

---

## admin_contracts.html — 계약 관리 목록

### P1. 참여자 셀 버튼 과밀 (사용성) ✅
- **수정:** 링크복사/재전송 버튼을 hover 시에만 표시 (모바일에서는 항상 표시)
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P2. 관리 컬럼 버튼 최대 5개 — 모바일 깨짐 (모바일) ✅
- **수정:** 768px 이하에서 기존 버튼 숨기고 "⋯" 드롭다운 메뉴로 통합, 외부 클릭 시 닫힘
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P3. 통계 카드 "예약발송" 색상 인라인 (일관성) ✅
- **수정:** 인라인 `style="color:#4338ca;"` → `.stat-card.stat-scheduled` CSS 클래스
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P3. 날짜 범위 "~" 구분자 모바일 깨짐 (모바일) ✅
- **수정:** `.date-sep` 클래스 추가, 600px 이하에서 `display: none`
- **완료:** 커밋 `d85e4a0` (2026-02-26)

### P3. 검색 돋보기 이모지 렌더링 (접근성/렌더링) ✅
- **수정:** `content: '\1F50D'` 이모지 → CSS `mask` SVG 아이콘으로 교체 (크로스 브라우저 통일)
- **완료:** 커밋 `d85e4a0` (2026-02-26)

---

## UI/UX 요약

| 우선순위 | 파일 | 이슈 | 상태 |
|---------|------|------|------|
| P0 | contract_sign | 가짜 동의 → 실제 체크박스 | ✅ 완료 |
| P1 | contract_sign | 모달 버튼 순서 + 인라인 스타일 | ✅ 완료 |
| P1 | contract_create | role-dot 색상 하드코딩 | ✅ 완료 |
| P1 | admin_contracts | 참여자 셀 버튼 과밀 | ✅ 완료 |
| P2 | contract_create | 모바일에서 PDF 먼저 노출 | ⏸️ 보류 |
| P2 | admin_contracts | 관리 버튼 5개 모바일 깨짐 | ✅ 완료 |
| P2 | contract_create | 미리서명 버튼 터치 영역 부족 | ✅ 완료 |
| P3 | contract_sign | 다운로드 버튼 인라인 스타일 | ✅ 완료 |
| P3 | admin_contracts | 통계 카드 색상 인라인 | ✅ 완료 |
| P3 | admin_contracts | 날짜 "~" 모바일 깨짐 | ✅ 완료 |
| P3 | contract_create | label-input for 연결 누락 | ✅ 완료 |

---

## 전체 진행 현황

| 구분 | 전체 | 완료 | 보류 |
|------|------|------|------|
| 코드 리뷰 (치명적) | 3 | 3 | 0 |
| 코드 리뷰 (위험) | 5 | 5 | 0 |
| 코드 리뷰 (개선) | 5 | 3 | 1 (a11y) |
| UI/UX 리뷰 | 11 | 10 | 1 (모바일 PDF) |
| **합계** | **24** | **21** | **2** (+배포 1건 해당없음) |
