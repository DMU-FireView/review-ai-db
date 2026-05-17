# ai/rti_scoring.py
import json
from pathlib import Path

# [핵심] main.py로부터 분석 엔진과 포맷 변환 엔진을 다이렉트로 임포트!
from main import parse_raw_to_internal, analyze_single_review

INPUT_PATH = Path("data/normalized/reviews.json")
OUTPUT_PATH = Path("output/rti_results.json")

def calculate_rti(review_dict):
    # 1. raw 형태의 로컬 리뷰 데이터를 내부 ReviewInput 스키마로 정규화 변환
    internal_review = parse_raw_to_internal(review_dict)
    
    # 2. main.py에 탑재된 동일한 분석 알고리즘 엔진 작동
    analysis_result = analyze_single_review(internal_review)
    
    # 3. 로컬 저장 규격인 dict 형태로 안전하게 덤프하여 반환
    return analysis_result.model_dump()

def main():
    if not INPUT_PATH.exists():
        print(f"정규화 데이터가 없습니다: {INPUT_PATH}")
        return

    with INPUT_PATH.open("r", encoding="utf-8") as file:
        reviews = json.load(file)

    # 동일한 코어를 거쳐 전체 batch 데이터 분석
    results = [calculate_rti(review) for review in reviews]

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(results, file, ensure_ascii=False, indent=2)

    print(json.dumps(results[:5], ensure_ascii=False, indent=2))
    print(f"\n총 {len(results)}개 리뷰 RTI batch 분석 완료")

if __name__ == "__main__":
    main()
