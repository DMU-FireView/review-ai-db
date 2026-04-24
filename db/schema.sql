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
