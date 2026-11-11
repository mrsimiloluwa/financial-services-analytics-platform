# Data Classification & Information Security Policy

## 1. Classification Architecture

The platform categorizes all database assets, tables, columns, and metric outputs into four hierarchical governance sensitivity tiers:

```
[RESTRICTED]  -> Level 4: Passwords, tokens, API keys, private signing keys. Strictly prohibited in analytics.
     │
[CONFIDENTIAL] -> Level 3: Synthetic customer identifiers, account numbers, financial balances, amounts.
     │
 [INTERNAL]   -> Level 2: Model descriptions, metric formulas, schema lineage, platform documentation.
     │
  [PUBLIC]    -> Level 1: Public synthetic summaries, marketing descriptions, open API docs.
```

---

## 2. Sensitivity Tiers & Handling Rules

| Tier | Sensitivity Level | Description | Handling & Masking Rules |
| :--- | :---: | :--- | :--- |
| **`PUBLIC`** | 1 | Non-sensitive information suitable for open distribution. | No restriction on display, export, or usage. |
| **`INTERNAL`** | 2 | Platform definitions, metadata tags, metric schemas, and business glossaries intended for internal users. | Accessible across internal services and authenticated staff. Excluded from public external outputs. |
| **`CONFIDENTIAL`** | 3 | Customer identifiers, bank account holdings, transaction principal amounts, and fees. | Must be protected with role-based access. Raw customer identifiers are masked or redacted in AI context summaries. |
| **`RESTRICTED`** | 4 | Security credentials, database connection passwords, API signing tokens, and private keys. | **Strictly prohibited** in warehouse tables, analytical models, dbt artifacts, and logs. Any occurrence triggers automated redaction. |

---

## 3. Heuristic Pattern Detection & Inheritance

The `ClassificationEngine` assigns classifications through a 3-stage process:

1. **Explicit YAML Tagging**: If a dbt model or column defines `meta: {classification: 'CONFIDENTIAL'}` in its schema YAML, the explicit setting takes absolute precedence.
2. **Column Naming Heuristics**:
   - Fields matching `*customer_id*`, `*account_number*`, `*transaction_amount*`, `*opening_balance*` are automatically tagged **`CONFIDENTIAL`**.
   - Fields matching `*password*`, `*secret*`, `*token*`, `*api_key*` are automatically tagged **`RESTRICTED`**.
3. **Model-to-Column Inheritance**:
   - Raw database tables (`raw.*`) inherit **`CONFIDENTIAL`** by default.
   - Analytical models (`analytics.*`) inherit **`INTERNAL`** by default, with confidential attributes flagged at column level.
