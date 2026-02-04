# Track Specification: Token-Efficient Transaction Access

## Overview
This track focuses on improving the token efficiency of the MCP server when dealing with transaction data. Currently, agents often call `get_transactions` repeatedly or with overly broad parameters, leading to excessive token consumption and costs. We will implement more targeted filtering and specialized tools to allow agents to find exactly what they need with minimal overhead.

## Scope
- **Enhance `get_transactions`**: Add more granular filtering parameters. `search` and `category_id` will use the native SDK capabilities. `min_amount` and `max_amount` will be implemented as client-side filters within the MCP server to reduce output tokens.
- **New Tool: `search_transactions`**: A specialized wrapper around `get_transactions` optimized for text-based searches, ensuring relevant results are prioritized and extraneous fields are omitted if possible.
- **New Tool: `get_transaction_stats`**: A tool providing high-level aggregations (counts, sums, averages) for specific timeframes or categories. Since the upstream `get_transactions_summary` lacks filter support, this will be implemented by fetching data via `get_transactions` and aggregating it locally in the MCP server before returning the result to the LLM.

## Functional Requirements
1.  **Granular Filtering**: `get_transactions` must support `merchant_name` (via search or post-filter), `min_amount`, `max_amount`, and `category_id`.
2.  **Specialized Search**: `search_transactions` provides a direct interface for keyword lookup.
3.  **Lighter Analytical Queries**: `get_transaction_stats` returns specific metrics (count, sum, average) for filtered data sets without returning the transaction list itself.
4.  **SDK Alignment**: Use `monarchmoney` SDK filters where available (`search`, `category_ids`, `date_range`) and supplement with local logic where missing (`amount` range).

## Non-Functional Requirements
- **Token Efficiency**: Minimizing the payload returned to the LLM is the primary success metric.
- **Performance**: Local aggregation must be efficient enough not to cause timeouts for reasonable date ranges.

## Acceptance Criteria
- `get_transactions` correctly filters by `min_amount` and `max_amount`.
- `search_transactions` returns transactions matching the query string.
- `get_transaction_stats` returns correct `count`, `sum_income`, `sum_expense`, and `net` for a given date range and/or category.
