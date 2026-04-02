# Strategy Pseudocode

This is a manual high-level reconstruction from `.pyc` and disassembly.
It is not the original vendor source code.

## fetch_and_prepare_data
```python
def fetch_and_prepare_data(trade_size):
    if not fetch_data_lock.acquire(blocking=False):
        return None, None, None, None

    try:
        url = 'https://www.okx.com/api/v5/market/candles'
        params = {'instId': 'XAU-USDT-SWAP', 'bar': '5m', 'limit': '50'}
        payload = requests.get(url, params=params).json()
        candles = payload['data']

        df = pd.DataFrame(
            candles,
            columns=[
                'timestamp', 'open', 'high', 'low', 'close',
                'volume', 'volume_currency', 'volume_usdt', 'volume_contracts'
            ],
        )
        df['timestamp'] = pd.to_datetime(pd.to_numeric(df['timestamp'], errors='coerce'), unit='ms')
        for col in ['open', 'high', 'low', 'close', 'volume']:
            df[col] = pd.to_numeric(df[col], errors='coerce').astype(float)
        df = df.sort_values('timestamp').reset_index(drop=True)

        df_with_state, up_signal, low_signal = add_indicators_rotate(df, trade_size)
        latest_version = get_latest_version()
        return df_with_state, latest_version, up_signal, low_signal
    except Exception as exc:
        log_print('Failed to load chart data: ' + str(exc))
        return None, None, None, None
    finally:
        fetch_data_lock.release()
```

## add_indicators_rotate
```python
def add_indicators_rotate(df, trade_size):
    # Build indicator columns
    df['RSI_14'] = ta.rsi(df['close'], length=16)  # literal 16 appears in bytecode
    df['Middle_Band'] = df['close'].rolling(window=20).mean()
    std_dev = df['close'].rolling(window=20).std()
    df['Upper_Band'] = df['Middle_Band'] + 2 * std_dev
    df['Lower_Band'] = df['Middle_Band'] - 2 * std_dev

    # Detect Bollinger breakouts and breakout groups
    df['Candle_break_Upperband'] = ...
    df['Candle_break_Lowerband'] = ...
    df['Upperband_group'] = ...
    df['Lowerband_group'] = ...

    # Pull current orders and positions from OKX
    orders = okx_trade.get_order_list(instType='SWAP', instId=symbol_name, state='live')
    positions = get_positions_safe(symbol_name)
    active_position = find_active_position(positions)

    # If a position was fully closed, reset Fibonacci/order state
    if position_closed_or_all_orders_closed(...):
        cancel_all_orders(...)
        N_order_reset(...)
        send_telegram_message_sync(...)

    # Build Fibonacci anchor points from recent upper/lower extremes
    upper_high = ...
    lower_low = ...
    fibo_levels = {
        '0.236': ..., '0.382': ..., '0.5': ..., '0.618': ..., '0.764': ...,
        '1.236': ..., '1.382': ..., '1.5': ..., '1.618': ...
    }

    # Apply swap strategy threshold and trend-only filters
    # swap strategy values observed: None / 1% / 2% / 3%
    # trend-only no-entry thresholds observed: 0.3 / 0.5 / 1 / 1.5 / 2 / 2.5
    fibo_entry = ...
    fibo_TP = ...
    no_entry_string = ...

    # Trigger reset when nth-entry / Bollinger-break conditions fire
    if nth_reset_condition(...):
        cancel_all_orders(...)
        N_order_reset(...)
        no_entry_string = 'nth_reset_triggered'

    return df, upper_high, lower_low
```

## analyze_data
```python
def analyze_data(data, up, low):
    position_response = okx_account.get_positions(instType='SWAP', instId=symbol_name)
    positions = position_response.get('data', []) if position_response else []

    # If a long or short position is already active, do not open a new one
    if positions and positions[0].get('posSide') in ('long', 'short'):
        return 'ExitAnt AI: Current position is in progress. Judgment will proceed after position is closed.'

    # Otherwise decide direction from strategy mode, signal side, and fibo state
    if excute_only_long and low and fibo_entry != 0:
        return 'open long rotate'
    if excute_only_short and up and fibo_entry != 0:
        return 'open short rotate'
    return 'stay'
```

## open_long_rotate / open_short_rotate
```python
def open_long_rotate(trade_size):
    if not order_execution_lock.acquire(blocking=False):
        return 'trade_order_locked'

    try:
        if check_setting_change_protection():
            return 'trade_setting_change_active'
        if duplicate_or_rate_limit_guard(...):
            return 'trade_duplicate_prevention'
        if has_active_orders() or has_active_orders_by_side('long'):
            return 'trade_open_orders_exist'

        current_positions = get_positions_safe(symbol_name)
        trade_contracts = USDT_to_Contracts(
            trade_size, leverage_global, current_price=get_safe_btc_price()
        )
        if invalid_contract_count(trade_contracts):
            return 'Invalid trade size from USDT_to_Contracts'

        entry_price = fibo_entry
        take_profit = fibo_TP
        if invalid_price_relationship(entry_price, take_profit, side='long'):
            return 'trade_no_valid_price'

        attach_algo = [{
            'attachAlgoClOrdId': 'botbuy' + random_string(),
            'tpTriggerPx': take_profit,
            'sz': str(trade_contracts),
            'tpOrdPx': ...
        }]
        result = okx_trade.place_order(
            instId=symbol_name,
            tdMode='cross',
            side='buy',
            ordType='limit',
            sz=str(trade_contracts),
            attachAlgoOrds=attach_algo,
            px=str(entry_price),
            posSide='long',
            clOrdId=random_string(),
        )
        if result.get('code') == '0':
            last_order_price = entry_price
            last_order_time = time.time()
            send_telegram_message_sync(...)
            return 'Long order successful (OKX)'
        handle_okx_error(result)
    finally:
        order_execution_lock.release()


def open_short_rotate(trade_size):
    # Same control flow as long entry, but with:
    # side='sell', posSide='short', attachAlgoClOrdId='botsell...'
    # and short-side price validation rules
    ...
```

## make_decision_and_execute
```python
def make_decision_and_execute(trade_size, leverage):
    retry_network_operation(set_leverage_operation, max_retries=3, delay=2)
    positions = retry_network_operation(get_positions_operation, max_retries=3, delay=2)
    balance = retry_network_operation(get_balance_operation, max_retries=3, delay=2)

    XAU_balance = extract_available_balance(balance)
    is_task_running = True

    data_pd, _, up, low = fetch_and_prepare_data(trade_size)
    advice = analyze_data(data_pd, up, low)

    if advice == 'open long rotate':
        return open_long_rotate(trade_size)
    if advice == 'open short rotate':
        return open_short_rotate(trade_size)
    return advice
```

## main runtime
```python
def main():
    read API_KEY / SECRET_KEY / PASSPHRASE / TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID
    if credentials are missing:
        start_telegram_bot()
        wait_for_telegram_setup()

    is_valid = validate_keys_logic(api_key, secret_key, passphrase)
    if not is_valid:
        stop_or_wait_for_reconfiguration()

    requests.post(FASTAPI_URL + '/server/okx', json={
        'okx_uid': uid,
        'uid': uid,
        'telegram_id': TELEGRAM_CHAT_ID,
        'points': ...,
        'program_excute': ...,
        'referral_code': referral_code,
    })

    cancel_all_orders_if_any()
    start_telegram_bot()

    spawn_thread(refresh_okx_client_periodically)
    spawn_thread(monitor_process_health)
    spawn_thread(telegram_health_monitor_thread)
    initialize_swap_strategy_monitor()
    initial_validation()

    ensure_auto_trading_loop_thread_is_running()

    while True:
        if check_swap_strategy_change():
            reset_fibonacci_state()
        validate_settings_and_notify()
        monitor_system_resources()
        restart_telegram_bot_if_needed()
        restart_auto_trading_loop_if_needed()
        check_version_and_notify_periodically()
        time.sleep(...)
```
