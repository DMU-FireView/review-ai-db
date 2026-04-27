def calculate_behavior_score(review):
    score = 100
    reasons = []

    verified_purchase = review.get("verified_purchase")
    repurchase = review.get("repurchase")
    free_trial = review.get("free_trial")
    reviews_written_today = review.get("reviews_written_today")
    image_count = review.get("image_count", 0)

    if verified_purchase is False:
        score -= 30
        reasons.append("구매 이력 미확인")
    elif verified_purchase == "unknown":
        score -= 10
        reasons.append("구매 여부 확인 불가")

    if free_trial is True:
        score -= 10
        reasons.append("체험단/무상 제공 리뷰 가능성")

    if reviews_written_today is not None and reviews_written_today >= 3:
        score -= 15
        reasons.append("동일 작성자의 같은 날짜 다수 리뷰 작성")

    if image_count == 0:
        score -= 5
        reasons.append("이미지 첨부 없음")

    if repurchase is True:
        score += 5
        reasons.append("재구매 리뷰 신호")

    return min(max(score, 0), 100), reasons
