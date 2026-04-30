# RRI-UX — Reverse Requirements Interview for UX Critique

**5 UX Personas × 7 UX Dimensions × 8 Flow Physics Axes** (v1.0).

RRI-UX critiques *the experience* before a pixel is drawn.  It runs
alongside or BEFORE code — not after — so UX anti-patterns are caught
in design, not in testing.

## 1. Triết lý — Flow Physics

> "Đừng hỏi *'giao diện có đẹp không'*.  Hãy hỏi *'người dùng có CHẢY
>  được trên giao diện này không?'*  — như nước chảy xuôi dòng."

Humans interact with interfaces by natural laws that RRI-UX calls
**Flow Physics**:

| Law                   | Implication                                                 |
|-----------------------|-------------------------------------------------------------|
| Visual gravity        | Eyes read L→R, T→B (F-pattern, Z-pattern)                   |
| Motion inertia        | If user is scrolling down, next step is DOWN — never UP     |
| Task direction        | Next step is RIGHT or BELOW current, never before           |
| Viewport limit        | If user can't see it, it doesn't exist                      |
| Interaction friction  | Every stray click / reverse scroll = friction to reduce     |

## 2. Five UX personas

| Icon | Persona           | Tư duy                                                     |
|:----:|-------------------|------------------------------------------------------------|
| 🏃   | Speed Runner      | "50 dòng cần duyệt — 30 phút — rồi chuyển việc."          |
| 👁️   | First-Timer       | "Vừa được invite.  Không biết nhấn vào đâu."              |
| 📊   | Data Scanner      | "500 dòng — tìm 5 bất thường — ra quyết định."           |
| 🔄   | Multi-Tasker      | "Đang edit, sếp gọi 15 phút — quay lại mọi thứ còn nguyên."|
| 📱   | Field Worker      | "Đang ở kho, tay cầm điện thoại, mạng 3G chập chờn."      |

## 3. Seven UX dimensions

| U  | Dimension                 | Asserts                                                 |
|----|---------------------------|---------------------------------------------------------|
| U1 | Flow Direction            | Next step where eye + hand are heading                  |
| U2 | Information Hierarchy     | Primary info > secondary > tertiary visually obvious    |
| U3 | Cognitive Load            | ≤ 7 ± 2 choices at any moment; chunk / progressive      |
| U4 | Feedback & State          | Every action → visible response < 100 ms                |
| U5 | Error Recovery            | Error says WHAT is wrong + WHAT to do to fix it         |
| U6 | Accessibility & Readability | Contrast ≥ 4.5, keyboard reachable, screen-reader OK   |
| U7 | Context Preservation      | Tabs, filters, scroll position, draft survive blur     |

## 4. Eight Flow Physics axes

1. **SCROLL** — forward scroll only; CTA never above visible area
2. **CLICK DEPTH** — ≤ 3 clicks to any destination
3. **EYE TRAVEL** — same-screen movement ≤ 1 diagonal
4. **DECISION LOAD** — 1 primary decision per viewport
5. **RETURN PATH** — clear way back / cancel / save-draft
6. **VIEWPORT** — critical CTA in first viewport on 1440 × 900
7. **VN TEXT** — layout holds longest Vietnamese string
8. **FEEDBACK** — toast / spinner / checkmark for every mutation

## 5. Four result levels

| Marker | Meaning                                                           |
|:------:|-------------------------------------------------------------------|
| 🌊     | FLOW — natural, no friction                                       |
| ⚠️     | FRICTION — works, but slows the user                             |
| ⛔     | BROKEN — user cannot complete the task without heroic effort      |
| 🔲     | MISSING — design never considered this scenario; feed to RRI      |

## 6. Output format — S→V→P→F→I

```
ID: [MODULE]-[DIMENSION]-[NUMBER]
Persona: [🏃|👁️|📊|🔄|📱]
S: Scenario từ góc nhìn persona
V: Vi phạm cụ thể (hoặc "None — đã FLOW")
P: Trục vi phạm + Dimension vi phạm
F: Giải pháp (đến component / CSS nếu có thể)
I: [P0|P1|P2|P3] — [FLOW|FRICTION|BROKEN|MISSING]
```

Template: `assets/templates/rri-ux-critique.md` — `/vibe-rri-ux`.

## 7. Five-phase workflow

```
1. SCAN     — Flow Map + Viewport Map cho mọi màn hình
2. INTERVIEW — 5 personas × 15-30 critique points mỗi persona
3. SCORE    — 7 dimensions × 8 axes, priority Frequency × Severity
4. FIX      — P0 (BROKEN) trước, P1 (universal friction) tiếp
5. VALIDATE — UX score per dimension + release gate
```

## 8. Release gate

All 7 UX dimensions ≥ 70 % FLOW; at least 5 / 7 ≥ 85 %; zero P0 items
in BROKEN state → 🟢 release.  Identical to RRI-T gate structure.

## 9. Vietnamese-specific UX patterns

* **Longest-string test** — `"Ứng dụng quản lý ngân sách doanh nghiệp
  theo kế hoạch ngân sách phát triển vùng Tây Nguyên"` must not
  clip / wrap awkwardly in any card / table cell / nav item.
* **Address complexity** — Tỉnh / Quận-Huyện / Phường-Xã cascade;
  Field Worker can't type, must select.
* **VND format** — dot-thousands (`1.234.567 ₫`), no leading zeros.
* **CCCD / CMND** — 12 / 9 digits, validate check-digit.
* **Date format** — `DD/MM/YYYY` primary, ISO in data only.

## 10. The 12 SaaS anti-patterns (canonical checklist)

Release-gate condition `0/12 violations` is enforced by
`methodology.evaluate_anti_patterns_checklist`.  Every refine and
verify run must score zero hits against this list.

| ID | Anti-pattern | Description | Detection hint |
|---|---|---|---|
| AP-01 | **Modal-on-load** | Popup chặn ngay khi vào trang chủ — phá vỡ Speed Runner flow | Hero section bị overlay che ≥ 1.5 s sau load |
| AP-02 | **Hidden CTA** | Primary action không xuất hiện trong viewport đầu tiên | CTA dưới fold trên viewport 1366×768 / 390×844 |
| AP-03 | **Reverse-scroll trap** | Bước tiếp theo nằm phía trên bước hiện tại; user phải scroll ngược | DOM order ≠ visual order, hoặc next-step ở `top < current.top` |
| AP-04 | **Form > 7 fields, no progressive disclosure** | Form dài không split wizard / accordion / tab | `<form>` có > 7 input visible cùng lúc, không có step indicator |
| AP-05 | **Dropdown > 15 items, no search** | Bắt user scroll danh sách lớn để tìm | `<select>` / combobox với > 15 option, không có filter input |
| AP-06 | **Empty state without guidance** | Hiển thị "Không có dữ liệu" không kèm CTA / hướng dẫn tiếp | Empty container không có button / link / illustration explainer |
| AP-07 | **Silent failure** | Hành động fail nhưng UI không feedback (toast, banner, error text) | Network 4xx/5xx mà không có DOM change ở `[role="alert"]` / toast region |
| AP-08 | **Lost session on accidental refresh** | Form / draft biến mất khi F5 hoặc back-forward | Không có `localStorage` / `sessionStorage` / autosave debounce |
| AP-09 | **Tab/filter state reset on navigation** | Filter, sort, pagination biến mất khi đổi tab hoặc back | URL không phản ánh filter; in-memory state only |
| AP-10 | **Touch target < 44 × 44 px** | Mobile bấm nhầm liên tục; vi phạm WCAG 2.5.5 | Computed click target box < 44 px ở viewport ≤ 480 px |
| AP-11 | **Date format ambiguity** | Không clarify `DD/MM/YYYY` vs `MM/DD/YYYY`; Field Worker confuse | Date input không có placeholder / aria-describedby nêu format VN |
| AP-12 | **VND format errors** | Số tiền hiển thị `1234567` thay vì `1.234.567 ₫`; thiếu hậu tố ₫ | Number rendering không qua `Intl.NumberFormat('vi-VN', { style: 'currency', currency: 'VND' })` |

All 12 IDs are stable; do not renumber.  Add new patterns as `AP-13+`.
