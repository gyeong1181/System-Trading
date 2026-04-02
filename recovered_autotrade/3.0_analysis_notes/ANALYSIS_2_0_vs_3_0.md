# ExitAnt OKX Autotrade 2.0 vs 3.0 Recovery Analysis

This report separates the `2.0 baseline` from the `3.0 recovered structure`.
It is based on local Docker image extraction and bytecode-level inspection, not vendor source recovery.

## Scope

- 2.0 image: `exitant/autotrade-app-okx-2.0-gold:latest`
- 3.0 image: `exitant/exitant-okx-3.0:latest`
- Extracted binaries:
  - `recovered_autotrade/image_2_0/autotrade`
  - `recovered_autotrade/image_3_0/autotrade`
- Extracted entry modules:
  - `recovered_autotrade/image_2_0/autotrade2`
  - `recovered_autotrade/image_3_0/autotrade2`
- Extracted PYZ archives:
  - `recovered_autotrade/image_2_0/PYZ.pyz`
  - `recovered_autotrade/image_3_0/PYZ.pyz`

## Binary Facts

### 2.0

- ELF + PyInstaller onefile
- Size: `45,133,216`
- SHA-256: `a2b9fe1288556c60ab491238dd6fa4bf2959f54b49d50350f13ba294a941f5a2`
- Main script entry in TOC: `autotrade2`
- `autotrade2` compressed/uncompressed: `159,413 / 430,585`
- `PYZ.pyz` size: `9,509,731`

### 3.0

- ELF + PyInstaller onefile
- Size: `45,179,592`
- SHA-256: `fc694b3d78bff34bb85f4b784e17052bfad4a0dce9369138f8c855a83ebaf22c`
- Main script entry in TOC: `autotrade2`
- `autotrade2` compressed/uncompressed: `206,676 / 538,611`
- `PYZ.pyz` size: `9,509,749`

## Library Mapping

The embedded Python module surface is effectively unchanged between 2.0 and 3.0.

- `telegram`: 189 modules
- `okx`: 9 modules
- `candlelite`: 21 modules
- `paux`: 15 modules
- `pandas_ta_classic`: 162 modules
- `apscheduler`: 39 modules
- `httpx`: 24 modules
- `requests`: 17 modules
- `pandas`: 283 modules
- `numpy`: 117 modules
- `cryptography`: 53 modules
- `OpenSSL`: 5 modules

Important finding:

- `PYZ.pyz` module-name count is `1958` in both versions.
- There are `0` module-name additions and `0` removals in the embedded PYZ table.
- Therefore the large behavioral delta is concentrated in the main strategy entry script `autotrade2`, not in a new dependency set.

## 2.0 Baseline

### Default market model

- Default symbol: `XAU-USDT-SWAP`
- Core strategy components observed in bytecode:
  - RSI
  - Bollinger Band breakout grouping
  - Fibonacci anchor and entry/TP levels
  - swap-threshold expansion
  - trend-only no-entry filters
- Decision outputs:
  - `open long rotate`
  - `open short rotate`
  - `stay`

### 2.0 execution flow

`main`
-> `validate_keys_logic`
-> `start_telegram_bot`
-> `start_auto_trading_after_mode_check`
-> `auto_trading_loop`
-> `make_decision_and_execute`
-> `fetch_and_prepare_data`
-> `add_indicators_rotate`
-> `analyze_data`
-> `open_long_rotate` / `open_short_rotate`

### 2.0 structural characteristics

- Single global trading loop model
- Single global symbol context
- Global-state driven functions
- Global order lock / global order sizing
- Telegram-driven setup and control
- `auto_trading_loop` enforces single active loop and restarts itself on failure

### 2.0 important functions

- `fetch_and_prepare_data(trade_size)`
- `add_indicators_rotate(df, trade_size)`
- `analyze_data(data, up, low)`
- `open_long_rotate(trade_size)`
- `open_short_rotate(trade_size)`
- `make_decision_and_execute(trade_size, leverage)`
- `auto_trading_loop()`
- `main()`

## 3.0 Recovered Structure

### Default market model

3.0 no longer boots around `XAU` as the default symbol.

- Default symbol: `BTC-USDT-SWAP`
- Supported symbol table embedded in bytecode:
  - `BTC-USDT-SWAP`
  - `XAU-USDT-SWAP`
  - `XAG-USDT-SWAP`
  - `GOOGL-USDT-SWAP`
  - `NVDA-USDT-SWAP`
  - `QQQ-USDT-SWAP`
  - `SPY-USDT-SWAP`
  - `TSLA-USDT-SWAP`

Each supported symbol has embedded metadata:

- `instId`
- multilingual `display`
- `contract_size`
- `price_round`
- `lot_size`
- `min_size`
- `emoji`

### New state model

3.0 introduces a symbol-scoped runtime object:

- `SymbolState(symbol_key, trade_size, settings)`

Recovered `SymbolState` responsibilities:

- per-symbol `instId/config`
- per-symbol locks:
  - `state_lock`
  - `fetch_lock`
  - `order_lock`
- per-symbol settings:
  - `seed_size`
  - `leverage_global`
  - `change_position_value`
  - `entry_price_rotate`
  - `TP_price_rotate`
  - `extension`
  - `extension_trend_value`
  - `loss_ratio`
  - `side`
  - `fibo_swap_strategy`
  - `ai`
  - `close_first_TP`
  - `close_first_TP_rotate`
  - `first_close_entry`
  - `ai_strategy_type`
  - `target_yearly_return`
- per-symbol trade/fibonacci state:
  - `fibo_*`
  - `fibo_entry`
  - `fibo_TP`
  - `pre_fibo_entry`
  - `pre_fibo_TP`
  - `upper_high`
  - `lower_low`
  - `rotate_positions`
  - `trade_size_list`
  - `order_count`
  - `previous_position_count`
  - `position_total`
  - `paused`

### 3.0 execution flow

Single-symbol fallback path:

`main`
-> `start_telegram_bot`
-> `auto_trading_loop`
-> `make_decision_and_execute(trade_size, leverage, state)`
-> `fetch_and_prepare_data(trade_size, state)`
-> `add_indicators_rotate(df, trade_size, state)`
-> `analyze_data(data, up, low, state)`
-> `open_long_rotate(trade_size, state)` / `open_short_rotate(trade_size, state)`

Multi-symbol path:

`main`
-> `auto_trading_loop`
-> detect `symbol_states`
-> spawn `symbol_trading_loop(symbol_key)` per symbol
-> each thread:
  - reads `state = symbol_states[symbol_key]`
  - sets leverage using `state.instId`
  - calls `make_decision_and_execute(state.trade_size, state.leverage_global, state)`
  - logs checkpoints
  - restarts its own symbol thread if terminated unexpectedly

### 3.0 call-flow changes

These previously global functions now take `state` explicitly:

- `fetch_and_prepare_data`
- `add_indicators_rotate`
- `analyze_data`
- `close_long`
- `close_short`
- `open_long_rotate`
- `open_short_rotate`
- `make_decision_and_execute`
- `get_current_position_pnl`
- `get_current_status`
- `has_active_orders`
- `has_active_orders_by_side`
- `cancel_all_orders`
- `check_existing_position`
- `set_final_stop_loss_order`
- `USDT_to_Contracts`

This is the single biggest architectural shift in 3.0.

### 3.0 new control/config surface

New symbol-management and per-symbol setup functions:

- `show_symbol_selection`
- `handle_symbol_toggle`
- `confirm_symbol_selection`
- `show_seed_allocation`
- `handle_seed_quick_set`
- `_apply_seed_and_next`
- `show_multi_symbol_setup_intro`
- `show_multi_symbol_settings_select`
- `show_symbol_settings_detail`
- `handle_symbol_pause_toggle`
- `show_symbol_risk_select`
- `handle_symbol_risk_apply`
- `handle_symbol_setting_change`
- `apply_syms_text_input`
- `show_manage_symbols`
- `handle_sym_mgr_toggle`
- `handle_sym_mgr_done`
- `symbol_trading_loop`
- `save_symbol_state`
- `apply_symbol_state`

Recovered per-symbol setting key families:

- `syms_seed_*`
- `syms_lev_*`
- `syms_loss_*`
- `syms_dir_*`
- `syms_entry_*`
- `syms_ext_*`
- `syms_tp_*`
- `syms_trend_*`
- `syms_swap_*`
- `syms_ai_*`
- `syms_cage_*`
- `syms_vol_*`
- `syms_yearly_*`
- `syms_pause_*`
- `syms_reset_*`

### 3.0 strategy/config observations

High-confidence additions:

- Multi-symbol trading mode
- Symbol-scoped allocation and pause
- Seed allocation per symbol
- Asset-specific contract conversion via `contract_size`, `lot_size`, `min_size`, `price_round`
- Annual return targeting instead of the older monthly-return framing
- Per-symbol checkpoint logging
- Per-symbol thread auto-recovery

Indicator-level conclusion:

- Core signal stack still appears to be RSI + Bollinger + Fibonacci + swap strategy + trend-only filters.
- I did not find evidence of a brand-new indicator family being added at the dependency/module level.
- The meaningful 3.0 innovation is orchestration/state expansion, not a new TA library.

## Diff Report

### High-confidence technical differences

1. `single-symbol global state` -> `multi-symbol SymbolState architecture`
2. Default instrument changed from `XAU-USDT-SWAP` to `BTC-USDT-SWAP`
3. Tradable universe expanded to `BTC/XAU/XAG/GOOGL/NVDA/QQQ/SPY/TSLA`
4. Order sizing changed from a mostly global conversion path to symbol-aware conversion using:
   - `contract_size`
   - `lot_size`
   - `min_size`
   - `price_round`
5. Main loop changed from `one loop does all trading` to:
   - supervisor loop
   - symbol thread fan-out
   - symbol-thread restart on failure
6. Setup UX changed from one strategy profile to symbol-by-symbol configuration
7. Return model wording changed from monthly target selection to annual target selection

### Likely data-flow shift

2.0:

- Global settings
- Fetch XAU candles
- Calculate indicators
- Decide
- Submit order

3.0:

- Build `SymbolState`
- Resolve symbol metadata
- Allocate seed per symbol
- Spawn symbol thread
- Each symbol thread:
  - fetches candles for `state.instId`
  - computes indicators against symbol-local state
  - sizes order using symbol-local contract rules
  - logs checkpoints
  - manages recovery independently

### Likely call-stack shift

2.0:

- `auto_trading_loop -> make_decision_and_execute -> open_*`

3.0:

- `auto_trading_loop -> symbol_trading_loop -> make_decision_and_execute(state) -> open_*(state)`

This is not a cosmetic refactor. It is a runtime model change.

## 3.0 Pseudocode Reconstruction

```python
class SymbolState:
    def __init__(self, symbol_key, trade_size, settings):
        self.symbol_key = symbol_key
        self.config = SUPPORTED_SYMBOLS[symbol_key]
        self.instId = self.config["instId"]
        self.state_lock = threading.Lock()
        self.fetch_lock = threading.Lock()
        self.order_lock = threading.Lock()
        self.paused = False

        # per-symbol settings
        self.seed_size = settings.get("seed_size", trade_size)
        self.leverage_global = settings.get("leverage_global", 5)
        self.change_position_value = settings.get("change_position_value", 30)
        self.loss_ratio = settings.get("loss_ratio", 100)
        self.fibo_swap_strategy = settings.get("fibo_swap_strategy", 0)
        self.target_yearly_return = settings.get("target_yearly_return", 0)

        # per-symbol runtime state
        self.fibo_entry = 0
        self.fibo_TP = 0
        self.upper_high = 0
        self.lower_low = 0
        self.rotate_positions = []
        self.trade_size_list = []
        self.order_count = 0


def auto_trading_loop():
    if symbol_states:
        for sym_key in symbol_states:
            ensure_symbol_thread_running(sym_key)
        while trading_enabled:
            repair_dead_symbol_threads()
            sleep(30)
        return

    # fallback single-symbol mode
    acquire_singleton_loop_lock()
    while trading_enabled:
        refresh_okx_client()
        okx_account.set_leverage(instId=symbol_name, lever=str(leverage_global), mgnMode="cross", posSide="")
        make_decision_and_execute(trade_size_global, leverage_global)
        sleep_until_10s_boundary()


def symbol_trading_loop(symbol_key):
    state = symbol_states[symbol_key]
    while trading_enabled and not user_stopped_trading:
        if state.paused:
            sleep(5)
            continue

        okx_account.set_leverage(instId=state.instId, lever=str(state.leverage_global), mgnMode="cross", posSide="")
        make_decision_and_execute(state.trade_size, state.leverage_global, state)
        sleep_until_10s_boundary(min_sleep=3.0)


def make_decision_and_execute(trade_size, leverage, state):
    retry_network_operation(set_leverage_operation)
    positions = retry_network_operation(get_positions_operation)
    balance = retry_network_operation(get_balance_operation)

    data, _, up, low = fetch_and_prepare_data(trade_size, state)
    advice = analyze_data(data, up, low, state)

    if advice == "open long rotate":
        log_trading_checkpoint(state, "entry")
        return open_long_rotate(trade_size, state)
    if advice == "open short rotate":
        log_trading_checkpoint(state, "entry")
        return open_short_rotate(trade_size, state)

    log_trading_checkpoint(state, "calculation")
    return advice


def fetch_and_prepare_data(trade_size, state):
    candles = requests.get(
        "https://www.okx.com/api/v5/market/candles",
        params={"instId": state.instId, "bar": "5m", "limit": "50"},
    ).json()["data"]
    df = build_dataframe(candles)
    return add_indicators_rotate(df, trade_size, state)


def add_indicators_rotate(df, trade_size, state):
    symbol_name_local = state.instId
    current_price = get_safe_market_price(symbol_name_local)
    # same indicator family as 2.0:
    # RSI + Bollinger + Fibonacci + swap strategy + trend-only gating
    # but all fibo/order variables now live on `state`
    ...


def USDT_to_Contracts(target_margin_usdt, leverage, state):
    inst_id = state.instId if state else symbol_name
    contract_size = state.config["contract_size"]
    lot_size = state.config["lot_size"]
    min_size = state.config["min_size"]
    market_price = get_safe_market_price(inst_id)
    # symbol-aware contract count rounding
    ...
```

## Confidence Notes

High confidence:

- multi-symbol architecture
- `SymbolState` existence and field families
- supported instrument table
- symbol-thread supervisor model
- default symbol shift `XAU -> BTC`
- external dependency surface unchanged

Medium confidence:

- exact 3.0 order validation details inside `open_long_rotate/open_short_rotate`
- exact branch conditions inside `add_indicators_rotate`
- exact annual-return preset mapping logic

Low confidence:

- perfect line-for-line source reconstruction
- vendor comments / original variable naming intent
