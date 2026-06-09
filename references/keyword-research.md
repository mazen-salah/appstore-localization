# Per-storefront keyword research & validation (Astro ASO MCP)

The App Store keyword field is **not** translated — it is rebuilt per storefront
from real search data, then **validated** against Astro's popularity/difficulty
numbers before you commit it. Search demand differs by language and country, so a
literal translation of your English keywords leaves ranking on the table.

App Store indexes **name + subtitle + keywords as one word-bag**, so never repeat a
word that's already in the localized name/subtitle, and never waste characters on
spaces — `a,b,c`, not `a, b, c`. Hard limit: 100 characters.

## Tools
| Tool | Use |
| --- | --- |
| `mcp__astro-aso__get_keyword_suggestions` | AI suggestions for the app, per store, with popularity / difficulty / app-count |
| `mcp__astro-aso__search_app_store` | who ranks for a term in a store (find competitors) |
| `mcp__astro-aso__extract_competitors_keywords` | mine keyword ideas from apps ranking for a seed term |
| `mcp__astro-aso__add_keywords` | **validation** — batch-add candidate keywords for the store; returns real popularity, difficulty and your ranking |
| `mcp__astro-aso__search_rankings` | check ranking/popularity (with `includeStatistics` for trend/volatility) |
| `mcp__astro-aso__get_app_keywords` | list what's already tracked |
| `mcp__astro-aso__remove_keywords` | drop rejected candidates (destructive — list them and confirm first) |

## Workflow per locale

### 1. Discover candidates
- `get_keyword_suggestions(store=<cc>, appId=<id>, highPopularity=true)` for a
  ranked starting set in that store's language.
- For your strongest seed terms, `extract_competitors_keywords(keyword, store)`
  and `search_app_store(keyword, store, appId=<id>)` to mine what competitors rank
  for and where you'd stand.

### 2. Validate the candidate set (this is the step that matters)
Batch the candidate localized keywords through `add_keywords(keywords=[...],
store=<cc>, appId=<id>)`. Astro returns, per keyword, its **popularity**,
**difficulty**, and your app's current **ranking**. This is the same validation
pass you'd do by hand in the Astro dashboard.

Select by **popularity vs difficulty**:
- Keep high-popularity terms you can realistically rank for (low/medium difficulty
  for a new app).
- Drop near-zero-popularity terms (they waste characters) and brutally hard,
  high-difficulty heads unless you have authority.
- Use `search_rankings(keyword, store, includeStatistics=true)` to sanity-check
  trend/volatility on the few you're unsure about.
- `remove_keywords` the rejected candidates from tracking (optional housekeeping;
  confirm the list first — it's destructive).

### 3. Pack the field
Assemble the surviving terms into a comma-separated, **no-spaces**,
single-/multi-word string ≤100 chars, excluding any word already in the localized
`name`/`subtitle`. Write to `ios/fastlane/metadata/<locale>/keywords.txt`.

### 4. Lint
`python scripts/check_metadata.py ios/fastlane/metadata --locale <cc>` flags
over-length, wasted spaces, duplicates, and name/subtitle redundancy. Re-pack
until clean.

## Notes
- Track the app first if needed: `mcp__astro-aso__list_apps` →
  `mcp__astro-aso__add_app(appStoreId=...)`.
- Re-validate periodically — popularity shifts; today's good anchor can fade.
- If the Astro MCP isn't connected, you can still translate keywords, but say so:
  you lose the data-driven ranking edge and are guessing at demand.
