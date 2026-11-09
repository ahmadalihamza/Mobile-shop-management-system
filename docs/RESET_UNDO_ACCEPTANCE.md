# Mobile Desk 1.3.0 — owner reset and entry undo

Requested behaviour: let the client reverse mistaken saved entries and start completely fresh during learning, while restricting full cleanup to an owner with credentials.

## Delivered behaviour

- Sidebar Undo Last Entry reviews the exact last saved supported business transaction and requires a correction reason. Selected sale/purchase corrections are labelled Undo selected entry. Original records remain marked Voided; stock and attached payments are reversed through existing trading rules. Used purchase stock and active invoice returns continue to block unsafe reversal.
- Settings → Owner & Reset provides owner username/password setup, authenticated password change and Reset All Business Data. There is no default password and reset stays disabled until owner setup. Daily trading does not prompt for owner login.
- Reset needs credentials and the literal RESET confirmation. A consistent, validated safety backup is saved before replacement. All business records and balances become zero; shop settings, account names, reference catalogue, owner credentials and old backups remain. Backup restore also requires configured credentials in the UI and enforces them in the service when protection exists.
- Owner protection is outside the replaceable data directory and backup payload, so an older backup cannot disable it. Passwords are salted scrypt hashes, compared in constant time; repeated failures are rate-limited across restarts. Unreadable security configuration fails closed. Windows administrators with filesystem access remain outside this local application authorization boundary.
- The reset/restore staging protocol recovers the original files after verification failure or an interrupted directory swap. A failed backup prevents reset. The owner can restore the automatically saved backup to undo a full reset.
- Monthly report dates give a fresh monthly view while stock and debts continue. The reset screen explicitly explains this so a routine month change does not encourage clearing real balances.

## Verification

Automated tests cover password setup/change and persistent attempt limits, absent/incorrect credentials, confirmation, damaged security configuration, old-backup protection, reset to zero, retained configuration/catalogue, backup failure, post-swap rollback, restoration of cleared records, audited transaction undo and dependencies, stale undo confirmation, cancelled forms and actual Qt dialog submissions. The complete result is recorded in docs/qa/tests.xml.

The isolated native release diagnostic submits owner setup, undoes an expense, rejects a wrong reset password, performs an authorized full reset and restores the exact pre-reset stock/customer/supplier balances. Its captured dialogs and smoke-result.json document source, packaged and installed checks. No test reset runs against the client's actual data directory.

Password primitives follow Python's [hashlib documentation](https://docs.python.org/3.12/library/hashlib.html#key-derivation) and [hmac comparison documentation](https://docs.python.org/3.12/library/hmac.html#hmac.compare_digest).
