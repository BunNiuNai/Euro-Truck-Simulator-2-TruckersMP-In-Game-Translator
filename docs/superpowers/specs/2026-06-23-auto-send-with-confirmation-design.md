# Auto-Send with Chat Log Confirmation — Design Spec

**Date:** 2026-06-23
**Status:** approved
**Reference:** Seven-TMP/ets2-chat-translator compose pipeline

## Goal

Replace the current semi-manual compose→send flow with a fully automatic pipeline:
user types Chinese → Enter → translate → **auto-send to game chat** → **confirm via chat log** → show result.

## Current Flow (BEFORE)

```
User presses Shift+Y → input bar shows
  → types Chinese → Enter
  → _do_translate() on background thread
  → _on_translate_done(): fills entry with English, selects text
  → [USER MUST MANUALLY:]
      → Ctrl+C copy
      → Alt+Tab to game
      → Y to open chat
      → Ctrl+V paste
      → Enter send
      → press enter_hotkey to confirm sent
```

## Target Flow (AFTER)

```
User presses Shift+Y → input bar shows
  → types Chinese → Enter
  → _do_translate() on background thread
  → _on_translate_done() calls ComposeSender.send():
      1. Validate translation (not empty, not same as input, not still Chinese)
      2. Save clipboard content
      3. Hide overlay window ← NEW
      4. Send to game via input_sender.send_chat_message() ← NEW (was manual)
      5. Wait for chat log confirmation (2.5s timeout) ← NEW
      6. Restore clipboard ← NEW
      7. Restore overlay window
      8. Return status to overlay
  → _insert_sent() + show result status in hint label
```

## Architecture

New module: `compose_sender.py`

```
compose_sender.py  ──depends on──→  input_sender.py  (send_chat_message, clipboard_*)
                   ──depends on──→  monitor.py       (via raw_queue for confirmation)
                   ──holds weakref──→  overlay.py     (hide/show window)

overlay.py         ──calls──→  compose_sender.ComposeSender.send()
```

## ComposeSender Class

### Signature

```python
class ComposeSender:
    def __init__(self, cfg: AppConfig, raw_queue: Queue, overlay_ref)
    def send(self, chinese: str, english: str) -> SendResult
```

### SendResult Enum

```
OK_CONFIRMED      — sent + confirmed by chat log
OK_UNCONFIRMED    — sent but not confirmed within 2.5s
FAIL_SEND         — send_chat_message returned error
FAIL_TRANSLATION  — translation was empty / same as input / still mostly Chinese
BUSY              — another compose is in progress (thread-safe guard)
```

### _validate(english, chinese) → bool

- Reject if `english` is empty
- Reject if `english.strip() == chinese.strip()`
- Reject if >30% of characters in `english` are CJK (hex 4e00-9fff)

### _wait_confirmation(text, timeout=2.5) → bool

- Subscribe to `raw_queue` (the Queue between monitor → translator)
- For each ChatMessage pulled from the queue:
  - Skip if `msg.is_self == True`
  - Normalize both msg.text and the sent text (collapse whitespace, trim)
  - If match → return True
- If timeout → return False
- Uses `raw_queue.get(timeout=0.1)` in a polling loop to avoid blocking indefinitely

### _normalize(text) → str

```python
re.sub(r'\s+', ' ', text).strip()
```

### Thread Safety

- Class-level `threading.Lock()` on `send()`
- If lock cannot be acquired immediately → return `SendResult.BUSY`
- This prevents double-submit (user pressing Enter twice rapidly)

## overlay.py Changes

### _on_translate_done() — rewrite

Remove: manual send poller start, entry box fill with English text
Add: ComposeSender call, result handling, status display

### Removals

- `_start_manual_send_poller()` method
- `_stop_manual_send_poller()` method
- `_on_copy_hotkey()` method
- `_on_enter_hotkey()` method
- `_manual_poller_active` attribute
- `_pending_chinese`, `_pending_english` attributes (moved to ComposeSender)

### Keep

- `_do_translate()` — unchanged
- `_on_translate_error()` — unchanged
- `_insert_sent()` — unchanged
- `_focus_send_entry()` — unchanged (still used to show input bar)

### Constructor change

Accept `raw_queue` parameter:

```python
def __init__(self, cfg, message_queue, stats_ref=None, raw_queue=None):
    self.raw_queue = raw_queue  # NEW — for ComposeSender
```

## hotkey_manager.py Changes

### Removals

- `start_manual_send()` method
- `stop_manual_send()` method
- `_manual_poller_active` attribute
- `_pending_chinese`, `_pending_english` attributes

## main.py Changes

Pass `raw_queue` to OverlayWindow:

```python
self.overlay = OverlayWindow(self.cfg, self.display_queue, self.translator.stats, self.raw_queue)
```

## Edge Cases

| Scenario | Behavior |
|:---|:---|
| User presses Enter twice rapidly | `_busy` lock → second call returns BUSY, ignored |
| Game not running / chat not open | `send_chat_message()` fails → return FAIL_SEND |
| Game window lost focus during send | Best-effort via existing `_focus_send_entry` tricks |
| Clipboard had important content | Saved before send, restored after |
| Translation is garbage | `_validate()` catches it → FAIL_TRANSLATION |
| Overlay hidden by user during send | `show()` restores it unconditionally |
| Chat log confirmation times out | Return OK_UNCONFIRMED, still show message in UI |
| raw_queue has hundreds of messages | `get(timeout=0.1)` skips fast; max 25 polls in 2.5s |
| User's own message enters the queue | `is_self` check skip prevents false confirmation |

## Files Changed

| File | Action | Lines |
|:---|:---|:---|
| `compose_sender.py` | **CREATE** | ~130 |
| `overlay.py` | Modify `_on_translate_done`, remove manual send code, add raw_queue param | ~30 changed, ~60 removed |
| `hotkey_manager.py` | Remove manual send methods | ~50 removed |
| `main.py` | Pass raw_queue to OverlayWindow | 1 changed |

## Non-Goals

- NOT changing the Shift+Y input bar UX (still pop-up style)
- NOT adding search/filter to the overlay
- NOT changing translation backend or provider logic
- NOT attempting game window activation from external process (stays best-effort as-is)

## Testing

- Unit test: `ComposeSender._validate()` with various inputs
- Unit test: `ComposeSender._normalize()` with whitespace variants
- Unit test: `ComposeSender._wait_confirmation()` with a mock queue
- Manual test: full flow with ETS2 + TruckersMP running
