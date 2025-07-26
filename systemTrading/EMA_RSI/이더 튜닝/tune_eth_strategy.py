from skopt import gp_minimize
from skopt.space import Real, Integer

# 튜닝 범위 설정
space = [
    Real(5, 10, name='TP'),         # TP 5% ~ 10%
    Real(1, 5, name='SL'),          # SL 1% ~ 5%
    Integer(3, 10, name='EMA_fast'), # 단기 EMA 3 ~ 10
    Integer(15, 30, name='EMA_slow'), # 장기 EMA 15 ~ 30
    Real(50, 60, name='RSI_threshold'), # RSI 50 ~ 60
    Real(1.0, 2.0, name='Volume_filter'), # 거래량 필터 1.0 ~ 2.0
    Integer(2, 10, name='Max_holding_period') # 보유 기간 2 ~ 10시간
]

# 백테스트 결과 입력 함수
def objective(params):
    tp, sl, ema_fast, ema_slow, rsi, vol_filter, max_hold = params
    print(f"테스트: TP={tp}%, SL={sl}%, EMA_fast={ema_fast}, EMA_slow={ema_slow}, RSI={rsi}, Vol={vol_filter}, Hold={max_hold}")
    sharpe = float(input("샤프 비율: "))
    win_rate = float(input("승률(%): ")) / 100  # 백분율 -> 소수로
    mdd = float(input("MDD(%): ")) / 100       # 백분율 -> 소수로
    adjusted_sharpe = (sharpe * win_rate) / (mdd + 1)
    return -adjusted_sharpe  # 최대화하려고 음수로

# 튜닝 실행
result = gp_minimize(objective, space, n_calls=20, random_state=42)
best_params = result.x
print(f"최적 전략: TP={best_params[0]}%, SL={best_params[1]}%, EMA_fast={best_params[2]}, EMA_slow={best_params[3]}, RSI={best_params[4]}, Vol={best_params[5]}, Hold={best_params[6]}")
print(f"최고 조정된 샤프 비율: {-result.fun}")