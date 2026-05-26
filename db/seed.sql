INSERT OR REPLACE INTO products (
    product_id,
    name,
    product_url,
    category
)
VALUES
(
    '53530143052',
    'SOUNDPRO ANC 노이즈캔슬링 블루투스 이어폰 X7 Pro',
    'https://smartstore.naver.com/main/products/11590446932',
    '전자기기'
);

INSERT OR REPLACE INTO reviews (
    review_id,
    product_id,
    user_id,
    rating,
    content,
    review_date,
    verified_purchase,
    account_age_days,
    reviews_written_today,
    similar_review_count
)
VALUES
(
    1,
    '53530143052',
    'reviewer_0099',
    5,
    '이 제품 정말 최고예요. 품질 완전 대박. 이런 제품은 처음봐요. 품질 완전 대박. 강력추천!!',
    '2026-05-25',
    FALSE,
    2,
    12,
    8
),
(
    2,
    '53530143052',
    'kim_realbuyer',
    4,
    '배송도 빠르고 품질도 좋네요. 다만 색상이 사진과 조금 달라서 별 하나 뺐어요. ANC 성능은 지하철에서 꽤 괜찮았습니다.',
    '2026-05-24',
    TRUE,
    540,
    1,
    0
),
(
    3,
    '53530143052',
    'new_user_102',
    5,
    '전반적으로 만족합니다. 음질도 괜찮고 착용감도 좋아요. 추천드립니다.',
    '2026-05-23',
    FALSE,
    15,
    3,
    1
);