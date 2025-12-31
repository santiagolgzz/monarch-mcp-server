"""Script to add safety decorators to write operations."""

# List of (line_number, function_name, safety_description) for operations needing decorators
operations_to_update = [
    ('delete_transaction_category', '@mcp.tool()\ndef delete_transaction_category', '@mcp.tool()\n@require_safety_check("delete_transaction_category")\ndef delete_transaction_category', 'Safety: Rate limited to 5/min'),
    ('delete_transaction_categories', '@mcp.tool()\ndef delete_transaction_categories', '@mcp.tool()\n@require_safety_check("delete_transaction_categories")\ndef delete_transaction_categories', 'Safety: Rate limited to 2/min, 10/day - DESTRUCTIVE'),
    ('create_manual_account', '@mcp.tool()\ndef create_manual_account', '@mcp.tool()\n@require_safety_check("create_manual_account")\ndef create_manual_account', 'Safety: Rate limited to 3/min'),
    ('delete_account', '@mcp.tool()\ndef delete_account', '@mcp.tool()\n@require_safety_check("delete_account")\ndef delete_account', 'Safety: Rate limited to 2/min, 5/day - DESTRUCTIVE'),
    ('update_account', '@mcp.tool()\ndef update_account', '@mcp.tool()\n@require_safety_check("update_account")\ndef update_account', 'Safety: Rate limited to 10/min'),
    ('update_transaction_splits', '@mcp.tool()\ndef update_transaction_splits', '@mcp.tool()\n@require_safety_check("update_transaction_splits")\ndef update_transaction_splits', 'Safety: Rate limited to 10/min'),
    ('create_tag', '@mcp.tool()\ndef create_tag', '@mcp.tool()\n@require_safety_check("create_tag")\ndef create_tag', 'Safety: Rate limited to 10/min'),
    ('set_transaction_tags', '@mcp.tool()\ndef set_transaction_tags', '@mcp.tool()\n@require_safety_check("set_transaction_tags")\ndef set_transaction_tags', 'Safety: Rate limited to 20/min'),
    ('set_budget_amount', '@mcp.tool()\ndef set_budget_amount', '@mcp.tool()\n@require_safety_check("set_budget_amount")\ndef set_budget_amount', 'Safety: Rate limited to 10/min'),
    ('upload_account_balance_history', '@mcp.tool()\ndef upload_account_balance_history', '@mcp.tool()\n@require_safety_check("upload_account_balance_history")\ndef upload_account_balance_history', 'Safety: Rate limited to 2/min - CAUTION'),
]

# Read file
with open('src/monarch_mcp_server/server.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Apply replacements
for func_name, old_pattern, new_pattern, safety_note in operations_to_update:
    if f'@require_safety_check("{func_name}")' not in content:
        content = content.replace(old_pattern, new_pattern)
        # Also add safety note to docstring
        print(f'Added safety decorator to {func_name}')
    else:
        print(f'{func_name} already protected')

# Write back
with open('src/monarch_mcp_server/server.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('\nDone adding safety decorators!')
