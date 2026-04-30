# RRI-T — Reverse Requirements Interview for Testing

**5 Testing Personas × 7 Testing Dimensions × 8 Stress Axes** (v1.0).

RRI-T is the **quality-verification** counterpart of RRI: after the
Builder ships a TIP, RRI-T proves the build is *correct* AND uncovers
things the requirements never contemplated.

## 1. Five testing personas

| Icon | Persona             | Tư duy                                                                       |
|:----:|---------------------|------------------------------------------------------------------------------|
| 👤   | End User Tester     | "Mỗi sáng mở app tôi làm gì? Tôi cần gì để không phải suy nghĩ nhiều?"       |
| 📋   | Business Analyst    | "Mọi business rule phải chính xác. Mọi con số phải khớp."                     |
| 🔍   | QA Destroyer        | "Mọi thứ có thể sai SẼ sai. Tôi tìm mọi cách phá hệ thống."                  |
| 🛠️   | DevOps Tester       | "Dev máy chạy đúng — production chết. Tôi test điều kiện thực tế."           |
| 🔒   | Security Auditor    | "Mọi input là hostile. Mọi user có thể là attacker."                         |

## 2. Seven testing dimensions

| D  | Dimension                    | What it asserts                                         |
|----|------------------------------|---------------------------------------------------------|
| D1 | UI / UX Testing              | Look & feel, accessibility, responsiveness              |
| D2 | API Testing                  | Contract, status codes, payload shape, idempotency      |
| D3 | Performance Testing          | Budgets + load scenarios + profiler evidence            |
| D4 | Security Testing             | OWASP top-10, authn/authz, data exposure, rate-limit    |
| D5 | Data Integrity Testing       | Business rules, referential integrity, ledger balances  |
| D6 | Infrastructure Testing       | Deploy, rollback, backup, migration, scaling            |
| D7 | Edge Case & Error Recovery   | Boundaries, empty, overflow, concurrency, graceful fail |

## 3. Eight stress axes

1. **TIME** — rapid sequential / long-duration / late-day load
2. **DATA** — boundary values, overflow, localized (VN) text
3. **ERROR** — network, permission, race, partial failure
4. **COLLAB** — concurrent users on the same resource
5. **EMERGENCY** — incident response, rollback under pressure
6. **SECURITY** — hostile inputs, token abuse, session theft
7. **INFRASTRUCTURE** — pod crash, DB failover, cache eviction
8. **LOCALIZATION** — Vietnamese text, VND, DD/MM/YYYY, CCCD/CMND

Combine axes: `DATA × TIME × LOCALIZATION` is a canonical stress recipe.

## 4. Four result levels

| Marker | Meaning                                                        |
|:------:|----------------------------------------------------------------|
| ✅     | PASS — behaviour matches spec                                  |
| ❌     | FAIL — behaviour violates spec                                  |
| ⚠️     | PAINFUL — passes spec but hurts the user (UX / ops friction)   |
| 🔲     | MISSING — spec didn't cover this; feed back to RRI             |

## 5. Output format — Q→A→R→P→T

```
ID: [MODULE]-[DIMENSION]-[NUMBER]
Persona: [👤|📋|🔍|🛠️|🔒]
Q: Câu hỏi từ góc nhìn persona
A: Expected behaviour
R: Requirement rút ra (maps back to REQ-*)
P: P0 | P1 | P2 | P3
T: TEST CASE
   Precondition: <setup>
   Steps:        1. … 2. … 3. …
   Expected:     <kết quả chi tiết>
   Dimension:    D1..D7
   Stress:       <axis list>
Result: [✅|❌|⚠️|🔲] <notes>
```

Template: `assets/templates/rri-t-test-case.md` — `/vibe-rri-t`.

## 6. Five-phase workflow

```
1. PREPARE   — thu requirements + setup test env + scope
2. DISCOVER  — 5 personas × 20-35 questions each   → 100+ test ideas
3. STRUCTURE — Map to 7 dimensions, prioritize Impact × Likelihood
4. EXECUTE   — Run P0 first, record 4-level result
5. ANALYZE   — Coverage matrix + release gate
```

## 7. Release gate

All **7 dimensions ≥ 70 %** PASS; at least **5/7 ≥ 85 %**; zero
P0 items in FAIL state → 🟢 release.  70-84 % → 🟡 conditional.
< 70 % → 🔴 blocked.

## 8. Vietnamese-specific testing

* Diacritic-insensitive search (`dự án ruff` ⇄ `du an ruff`)
* Layout with longest Vietnamese phrase (`Ứng dụng quản lý ngân sách…`)
* Currency `VND` with dot-thousands (`1.234.567 ₫`)
* Date `DD/MM/YYYY`, tax code 10 / 13 digits, CCCD 12 digits
* TCVN / ISO-8859-vn → UTF-8 migration edge cases
