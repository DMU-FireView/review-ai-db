# Crawler Raw JSON Schema 초안

## 문서 목적

크롤러가 수집한 리뷰 데이터를 DB에 바로 저장하지 않고 raw JSON으로 먼저 보존하면 원본 확인, 데이터 검증, converter 테스트 및 RTI 분석 재실행이 쉬워진다.

이 문서는 Re:view v1에서 크롤러가 생성할 raw JSON 구조의 초안을 정의한다. 실제 필드와 DB 매핑은 크롤러 구현 및 팀 협의 후 확정한다.

## 1. raw JSON이 필요한 이유

raw JSON을 크롤러와 DB 저장 사이의 중간 결과물로 사용하는 이유는 다음과 같다.

```text
- 크롤링 원본 데이터 보존
- converter 테스트 가능
- DB insert 전 데이터 검증 가능
- 크롤러 구조 변경 시 비교 가능
- 같은 raw JSON으로 RTI 분석 재실행 가능
- 팀원 간 데이터 형식 공유 가능
```

크롤링과 이후 분석 단계를 분리하면 외부 플랫폼 응답이나 크롤러가 변경되어도 저장된 원본 데이터를 기준으로 각 단계를 독립적으로 검증할 수 있다.

## 2. 전체 구조 초안

아래 구조를 v1 crawler raw JSON의 초안으로 제안한다.

```json
{
  "source": "naver",
  "mall": "NAVER",
  "crawled_at": "2026-06-09T12:00:00",
  "product": {
    "product_id": "7195971829",
    "product_name": "상품명",
    "product_url": "https://smartstore.naver.com/main/products/7195971829",
    "category": "unknown"
  },
  "reviews": [
    {
      "review_id": "1001",
      "user_id": "kim_**",
      "rating": 5,
      "content": "배송도 빠르고 상품도 좋아요",
      "review_date": "2026-05-01",
      "image_count": 1,
      "images": []
    }
  ]
}
```

필드명은 raw JSON과 converter 간 계약으로 사용될 수 있으므로 구현 전에 명명 방식과 선택 필드의 기본값을 합의해야 한다.

## 3. 상위 필드 설명

| 필드 | 설명 |
| --- | --- |
| `source` | 데이터를 수집한 크롤러 또는 원본 소스를 나타내는 값 |
| `mall` | 쇼핑몰 또는 플랫폼을 구분하는 표준 값 |
| `crawled_at` | 크롤링을 수행한 시각 |
| `product` | 리뷰 대상 상품의 식별 정보와 메타데이터 |
| `reviews` | 수집한 리뷰 객체의 배열 |

`source`는 크롤러 구현이나 원본 데이터 출처를 구분하고, `mall`은 서비스 내부에서 플랫폼을 일관되게 식별하는 용도로 사용할 수 있다.

## 4. product 필드 설명

| 필드 | 설명 |
| --- | --- |
| `product_id` | 쇼핑몰에서 사용하는 상품 고유 번호 |
| `product_name` | 크롤링 시점에 확인한 상품명 |
| `product_url` | 리뷰 수집 대상 상품 URL |
| `category` | 상품 카테고리이며, 확인할 수 없는 경우 `unknown` 등의 값 사용 가능 |

상품 관련 필드는 모든 리뷰에 반복하지 않고 상위 `product` 객체에 한 번만 저장한다.

## 5. review 필드 설명

| 필드 | 설명 |
| --- | --- |
| `review_id` | 플랫폼에서 식별 가능한 리뷰 고유 번호 |
| `user_id` | 리뷰 작성자 식별값 또는 공개된 작성자명 |
| `rating` | 리뷰 평점 |
| `content` | 리뷰 본문 |
| `review_date` | 리뷰 작성일 |
| `image_count` | 리뷰에 포함된 이미지 개수 |
| `images` | 이미지 URL 또는 이미지 메타데이터 배열 |

플랫폼에서 실제 사용자 ID를 제공하지 않는 경우 마스킹된 작성자명이나 공개된 작성자 식별값을 `user_id`로 사용할 수 있다.

## 6. 필수 필드 후보

AI 파트 기준으로 아래 필드를 v1 필수값 후보로 제안한다.

```text
product.product_id
product.product_url
reviews[].review_id
reviews[].user_id
reviews[].content
reviews[].review_date
```

`rating`, `image_count`, `images`는 플랫폼에 따라 제공되지 않을 수 있으므로 선택 필드로 둘 수 있다.

선택 필드가 없을 때 필드 자체를 생략할지, `null`, `0`, 빈 배열과 같은 기본값을 사용할지는 converter 구현 전에 합의해야 한다.

## 7. DB 매핑 후보

raw JSON을 정규화하여 DB에 저장할 때 아래와 같은 매핑을 후보로 고려할 수 있다.

```text
product.product_id → products.product_id
product.product_name → products.name 또는 product_name
product.product_url → products.product_url 또는 job product_url
reviews[].review_id → reviews.review_id
reviews[].user_id → reviews.user_id
reviews[].content → reviews.content
reviews[].review_date → reviews.review_date
reviews[].rating → reviews.rating
```

위 내용은 개념적인 매핑 후보이며, 실제 테이블 존재 여부와 DB 컬럼명 및 타입은 `schema.sql` 확인과 팀 협의 후 확정해야 한다.

## 8. converter와의 관계

raw JSON은 쇼핑몰별 원천 데이터를 공통 리뷰 구조로 변환하는 converter의 입력값이 될 수 있다.

예상 흐름은 다음과 같다.

```text
crawler raw JSON
→ converter
→ normalized reviews
→ DB insert
→ RTI analysis
```

converter는 raw JSON의 필수값을 검증하고, 선택 필드의 누락이나 플랫폼별 차이를 DB 및 RTI 분석에서 사용할 수 있는 공통 형식으로 정규화한다.

## 9. 협의 필요 항목

아래 항목은 raw JSON schema 및 converter 구현 전에 팀 협의가 필요하다.

```text
- user_id와 author 중 어떤 필드명을 사용할지
- review_date 형식을 YYYY-MM-DD로 통일할지
- product_url을 product JSON에만 둘지 job에도 저장할지
- image_count/images를 필수로 볼지
- rating이 없는 플랫폼 대응 방식
- raw JSON 저장 위치
```

날짜와 누락값 표현 방식은 converter 및 DB insert 동작에 직접 영향을 주므로 schema 확정 시 함께 정의해야 한다.

## 10. 결론

v1에서 raw JSON schema를 먼저 정하면 크롤러, converter, DB insert 및 RTI 분석을 하나의 구현에 결합하지 않고 독립적으로 테스트할 수 있다.

이를 통해 크롤러 구현이 변경되거나 일시적으로 실패하더라도 저장된 raw JSON과 샘플 데이터를 사용해 분석 파이프라인을 계속 검증할 수 있으므로 전체 개발 리스크를 줄일 수 있다.

이 문서는 협의를 위한 schema 초안이며 실제 API, DB schema, Redis/Worker 또는 크롤러 코드를 변경하지 않는다.
