# Product Guidelines

## Visual Identity & Data Presentation
- **Clarity & Precision**: All financial data (amounts, dates, account balances) must be presented with high precision. Use `YYYY-MM-DD` for all dates and ensure currency is clearly formatted.
- **Categorical Organization**: Group data logically (e.g., by account type, category group, or date) to ensure information is easy for the user to scan and understand.
- **Minimalist Professionalism**: Maintain a clean, professional appearance. Avoid excessive use of emojis or decorative elements that might distract from the financial data.

## Communication & Interaction Style
- **Data-Centric**: Focus on providing clear, accurate data. Since the tools are primarily for data access, communication should be direct and information-rich.
- **Functional Feedback**: Provide clear confirmation of successful operations and detailed, actionable error messages when things go wrong.

## Security & Safety
- **Credential Protection**: Absolute priority on data privacy. Under no circumstances should sensitive credentials like passwords, MFA codes, or raw session tokens be exposed in logs or tool outputs.
- **Destructive Operation Guards**: All destructive actions (deletes, bulk updates) must be gated by an explicit user approval mechanism to prevent accidental data modification.
- **Operational Auditability**: Every write operation must be logged locally with sufficient detail to allow the user to audit changes and perform manual or suggested rollbacks.
