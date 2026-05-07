import json
from pathlib import Path


INPUT_PATH = Path("output/rti_results.json")
OUTPUT_PATH = Path("output/rti_results_sample.json")


def load_results():
    if not INPUT_PATH.exists():
        print(f"RTI 결과 파일이 없습니다: {INPUT_PATH}")
        print("먼저 아래 명령어를 실행해주세요:")
        print("python ai/rti_scoring.py")
        return []

    with INPUT_PATH.open("r", encoding="utf-8") as file:
        return json.load(file)


def pick_samples(results):
    """
    팀원들이 보기 좋은 샘플을 추출합니다.

    기준:
    - safe / warn / danger가 있으면 등급별로 일부 추출
    - 현재 v0에서는 warn이 많을 수 있으므로 warn 중심으로도 추출
    - reasons가 다양한 리뷰를 우선 포함
    """

    samples = []

    safe_samples = [
        item for item in results
        if item.get("level") == "safe"
    ]

    warn_samples = [
        item for item in results
        if item.get("level") == "warn"
    ]

    danger_samples = [
        item for item in results
        if item.get("level") == "danger"
    ]

    # 등급별 샘플 우선 추가
    samples.extend(safe_samples[:2])
    samples.extend(warn_samples[:5])
    samples.extend(danger_samples[:3])

    # danger/safe가 없을 수 있으므로 부족하면 warn에서 추가
    if len(samples) < 10:
        existing_review_ids = {
            item.get("review_id")
            for item in samples
        }

        for item in warn_samples:
            if item.get("review_id") not in existing_review_ids:
                samples.append(item)
                existing_review_ids.add(item.get("review_id"))

            if len(samples) >= 10:
                break

    return samples[:10]


def main():
    results = load_results()

    if not results:
        return

    samples = pick_samples(results)

    with OUTPUT_PATH.open("w", encoding="utf-8") as file:
        json.dump(samples, file, ensure_ascii=False, indent=2)

    print(f"RTI 샘플 생성 완료: {OUTPUT_PATH}")
    print(f"샘플 개수: {len(samples)}개")

    level_count = {}

    for item in samples:
        level = item.get("level")
        level_count[level] = level_count.get(level, 0) + 1

    print("샘플 등급 분포:")
    print(json.dumps(level_count, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()