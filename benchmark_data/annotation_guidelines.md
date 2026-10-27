# Benchmark Annotation Guidelines

## Classes
Account, Billing, Technical, Other

## Decision Rules
1. Login/password/account access -> Account
2. Payment/bill/charge/subscription -> Billing
3. Error/crash/bug/feature broken -> Technical
4. Empty/gibberish/multi-issue/adversarial -> Other

## Ambiguous Cases
- "Payment failed due to technical error" -> Billing (payment is primary)
- "Account shows wrong balance after update" -> Technical (system caused issue)
- "Cannot access billing page" -> Technical (access issue)

## Limitations
- Single annotator, no IAA
- No adjudication process
- Some cases could have alternative valid labels