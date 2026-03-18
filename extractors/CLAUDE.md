# Extractor Layer Context

> Auto-loaded khi Claude Code làm việc trong extractors/
> Supplement root CLAUDE.md, không replace

## Extractor Status
<!-- context_manager.py update này tự động -->
| Platform | schema.py | extract.py | tests | Status |
|----------|-----------|------------|-------|--------|
| facebook | ✓ | ✓ | ✓ | DONE — 15/15 tests pass |
| google   | ○ | ○ | ○ | TODO — Phase 2 |
| tiktok   | ○ | ○ | ○ | TODO — Phase 2 |
| zalo     | ○ | ○ | ○ | TODO — Phase 2 |
| crm      | ○ | ○ | ○ | TODO — Phase 2 |

Legend: ○ TODO · ~ IN PROGRESS · ✓ DONE

## Reference Implementation
Always read `extractors/facebook/extract.py` before writing a new extractor.
It is the reference — follow its structure exactly.

## Layer-specific Gotchas
- FB: 3 lead action types — priority: `offsite_conversion.fb_pixel_lead` > `lead` > `onsite_web_lead`
- FB: leads=0 không có nghĩa no spend — check action_type, có thể là Traffic campaign
- FB: `spend` trả về dạng string từ API → coerce to float trong schema.py
- FB: ad account ID phải có prefix `act_` — extractor tự thêm, không cần trong .env
- FB: `time_range` dict (NOT `date_preset`) cho custom date range

## Current Focus
Working on: Phase 2 — Google Ads extractor (next)
