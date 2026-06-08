CREATE TABLE products (
    product_id VARCHAR(50) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE reviews (
    review_id BIGINT PRIMARY KEY,
    product_id VARCHAR(50) NOT NULL,
    user_id VARCHAR(100) NOT NULL,
    rating INT NOT NULL,
    content TEXT NOT NULL,
    verified_purchase BOOLEAN DEFAULT FALSE,
    account_age_days INT,
    reviews_written_today INT,
    similar_review_count INT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);

CREATE TABLE review_trust_scores (
    score_id BIGINT PRIMARY KEY,
    review_id BIGINT NOT NULL,
    rti INT NOT NULL,
    level VARCHAR(20) NOT NULL,
    text_score INT NOT NULL,
    behavior_score INT NOT NULL,
    network_score INT NOT NULL,
    reasons TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (review_id) REFERENCES reviews(review_id)
);


CREATE TABLE product_analysis_job (
    job_id VARCHAR(36) PRIMARY KEY COMMENT '작업 고유 ID (UUID 사용 권장)',
    mall VARCHAR(50) NOT NULL COMMENT '쇼핑몰 구분 (예: NAVER, OLIVEYOUNG)',
    product_id VARCHAR(100) NOT NULL COMMENT '해당 쇼핑몰의 상품 고유 번호',
    status VARCHAR(20) NOT NULL DEFAULT 'PENDING' COMMENT '진행 상태 (PENDING, RUNNING, DONE, FAILED)',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '작업 요청 시간',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '상태 마지막 갱신 시간',
    
    -- 검색 속도를 엄청나게 끌어올려 줄 인덱스(색인) 설정
    INDEX idx_mall_product (mall, product_id),
    INDEX idx_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='AI 리뷰 분석 비동기 작업 관리 테이블';