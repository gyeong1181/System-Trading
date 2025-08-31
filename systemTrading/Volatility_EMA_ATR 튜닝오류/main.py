import pandas as pd
from fetch_data import fetch_ohlcv
from walk_forward import walk_forward

def main():
    symbol = input("티커명을 입력하세요 (ex: BTC/USDT): ")
    timeframe = input("시간프레임 (예: 1h, 4h, 1d): ")
    days = int(input("백테스트 기간: 며칠? (예: 700): "))

    print("데이터를 불러오는 중입니다...")
    df = fetch_ohlcv(symbol, timeframe, since_days=days)
    print(f"총 {len(df)}개 데이터 로드 완료.")

    print("워크포워드 백테스트를 수행합니다...")
    wf_results = walk_forward(df)

    if wf_results.empty:
        print("백테스트 결과가 없습니다. 기간을 더 늘려보세요.")
        return

    print("\n[워크포워드 결과 요약]")
    print(wf_results.describe())

    # 샤프 ≥ 1 이상, 거래 횟수 5 이상인 결과만 필터링
    filtered = wf_results[(wf_results['sharpe'] >= 1) & (wf_results['trades'] >= 5)]
    
    if filtered.empty:
        print("유의미한 결과가 없습니다. 파라미터 또는 기간을 조정하세요.")
    else:
        best_overall = filtered.loc[filtered['sharpe'].idxmax()]
        print("\n[최적 파라미터 및 성과 - 필터된 결과 중 최고 샤프]")
        print(best_overall)

if __name__ == "__main__":
    main()
