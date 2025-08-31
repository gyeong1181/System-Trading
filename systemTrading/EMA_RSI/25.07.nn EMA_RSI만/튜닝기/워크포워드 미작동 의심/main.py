from fetch_data import fetch_ohlcv
from walk_forward import walk_forward

def main():
    symbol = input("티커명을 입력하세요 (ex: BTC/USDT): ").strip()
    timeframe = input("시간프레임 (예: 1h, 4h, 1d): ").strip()
    days = int(input("백테스트 기간(일): ").strip())

    print("데이터를 불러오는 중입니다...")
    df = fetch_ohlcv(symbol, timeframe, since_days=days)
    print(f"총 {len(df)}개의 데이터가 준비되었습니다.")

    print("워크포워드 백테스트를 시작합니다...")
    results = walk_forward(df)

    if results.empty:
        print("백테스트 결과가 없습니다. 기간 또는 파라미터를 조정해 주세요.")
        return

    print("\n[백테스트 결과 요약]")
    print(results.describe())

    filtered = results[(results['sharpe'] >= 1) & (results['trades'] >= 3)]
    if filtered.empty:
        print("유의미한 결과가 없습니다. 파라미터 또는 기간을 조정하세요.")
    else:
        best = filtered.loc[filtered['sharpe'].idxmax()]
        print("\n[최적 파라미터 및 성과]")
        print(best)

if __name__ == "__main__":
    main()
