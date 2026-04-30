"""Vietnamese-realistic data generator (v0.11.0, Phase α — F5b).

Produces realistic Vietnamese fake data for seeding, tests, and demo
content.  Inspired by taw-kit's ``faker-vi-recipes`` skill but extends
with:

- ``cccd()`` — Vietnamese 12-digit Citizen ID (CCCD/CMND format), with
  province prefix matching the reference table from Decision
  1383/QĐ-BCA.  No SSN — that's American.
- ``vnd_amount()`` — formats with the Vietnamese thousands separator
  (".") and the currency suffix "đ", honoring the reality that prices
  in Vietnam are written ``1.500.000đ`` not ``1,500,000 VND``.
- ``bank_account()`` — picks a real Vietnamese bank prefix (VCB / TCB
  / MB / ACB / BIDV / VPB) and an issue-bank-correct account length.
- ``phone()`` — guarantees an in-service Vietnamese mobile prefix as
  of 2024 (after the 2018 prefix migration).

The generator is **deterministic** when ``seed`` is supplied — useful
for snapshot tests.
"""

from __future__ import annotations

import dataclasses
import random
import string

# --- Reference data ---------------------------------------------------------
# Top family names (Wikipedia, ranked by population share).
_FAMILY_NAMES = (
    "Nguyễn",
    "Trần",
    "Lê",
    "Phạm",
    "Hoàng",
    "Huỳnh",
    "Phan",
    "Vũ",
    "Võ",
    "Đặng",
    "Bùi",
    "Đỗ",
    "Hồ",
    "Ngô",
    "Dương",
    "Lý",
    "Đào",
    "Đoàn",
    "Vương",
    "Trịnh",
)

# Common middle + given names — split by gender so output reads
# realistic.  This list is intentionally conservative: 30 male + 30
# female + 20 unisex middles.
_MIDDLE_M = ("Văn", "Hữu", "Quang", "Minh", "Đức", "Anh", "Thành", "Quốc", "Tuấn", "Bảo")
_MIDDLE_F = ("Thị", "Thu", "Ngọc", "Bích", "Diệu", "Thanh", "Hồng", "Phương", "Như", "Khánh")
_GIVEN_M = (
    "An",
    "Bình",
    "Cường",
    "Dũng",
    "Duy",
    "Hải",
    "Hùng",
    "Hiếu",
    "Khoa",
    "Kiên",
    "Long",
    "Lâm",
    "Minh",
    "Nam",
    "Phong",
    "Phú",
    "Quân",
    "Sơn",
    "Thắng",
    "Thịnh",
    "Tuấn",
    "Vinh",
    "Vũ",
    "Đức",
    "Hoàng",
    "Khánh",
    "Bách",
    "Trung",
    "Hiệp",
    "Tùng",
)
_GIVEN_F = (
    "An",
    "Anh",
    "Bích",
    "Châu",
    "Diệu",
    "Dung",
    "Đào",
    "Hà",
    "Hằng",
    "Hạnh",
    "Huyền",
    "Hương",
    "Khánh",
    "Lan",
    "Linh",
    "Mai",
    "My",
    "Ngân",
    "Ngọc",
    "Nhi",
    "Phương",
    "Quỳnh",
    "Tâm",
    "Thanh",
    "Thảo",
    "Trang",
    "Trinh",
    "Vân",
    "Yến",
    "Hà My",
)

# Vietnamese mobile prefixes (post-2018 migration, valid as of 2024).
# Source: Bộ Thông tin và Truyền thông announcement 2018.
_MOBILE_PREFIXES = (
    # Viettel
    "032",
    "033",
    "034",
    "035",
    "036",
    "037",
    "038",
    "039",
    "086",
    "096",
    "097",
    "098",
    # Vinaphone
    "081",
    "082",
    "083",
    "084",
    "085",
    "088",
    "091",
    "094",
    # MobiFone
    "070",
    "076",
    "077",
    "078",
    "079",
    "089",
    "090",
    "093",
    # Vietnamobile
    "052",
    "056",
    "058",
    "092",
    # Gmobile
    "059",
    "099",
)

# 63 provinces — top 12 most-populated for realistic distribution.
# Format: (CCCD prefix, province name)
_PROVINCES = (
    ("001", "Hà Nội"),
    ("079", "Thành phố Hồ Chí Minh"),
    ("031", "Hải Phòng"),
    ("048", "Đà Nẵng"),
    ("092", "Cần Thơ"),
    ("038", "Hà Tĩnh"),
    ("033", "Hưng Yên"),
    ("019", "Thái Nguyên"),
    ("056", "Khánh Hòa"),
    ("066", "Đắk Lắk"),
    ("075", "Đồng Nai"),
    ("077", "Bà Rịa - Vũng Tàu"),
)

_DISTRICTS_BY_PROVINCE = {
    "Hà Nội": (
        "Ba Đình",
        "Hoàn Kiếm",
        "Đống Đa",
        "Hai Bà Trưng",
        "Cầu Giấy",
        "Tây Hồ",
        "Long Biên",
        "Thanh Xuân",
        "Nam Từ Liêm",
        "Hà Đông",
    ),
    "Thành phố Hồ Chí Minh": (
        "Quận 1",
        "Quận 3",
        "Quận 7",
        "Quận Bình Thạnh",
        "Quận Phú Nhuận",
        "Quận Tân Bình",
        "Quận Gò Vấp",
        "Thành phố Thủ Đức",
    ),
    "Đà Nẵng": ("Hải Châu", "Thanh Khê", "Sơn Trà", "Ngũ Hành Sơn"),
}
_DEFAULT_DISTRICTS = ("Trung tâm", "Đông", "Tây", "Nam", "Bắc")

_STREET_NAMES = (
    "Nguyễn Trãi",
    "Lê Lợi",
    "Trần Hưng Đạo",
    "Hai Bà Trưng",
    "Phan Chu Trinh",
    "Lý Thường Kiệt",
    "Nguyễn Thị Minh Khai",
    "Cách Mạng Tháng 8",
    "Điện Biên Phủ",
    "Pasteur",
)

_BANK_PREFIXES = (
    ("VCB", 13),  # Vietcombank
    ("TCB", 12),  # Techcombank
    ("MB", 12),  # MB Bank
    ("ACB", 12),  # ACB
    ("BID", 14),  # BIDV
    ("VPB", 12),  # VPBank
    ("STB", 12),  # Sacombank
    ("TPB", 12),  # TPBank
)

_COMPANY_TYPES = ("Công ty TNHH", "Công ty Cổ phần", "Công ty TNHH MTV")
_COMPANY_KINDS = (
    "Thương mại",
    "Dịch vụ",
    "Công nghệ",
    "Đầu tư",
    "Phát triển",
    "Sản xuất",
    "Xuất nhập khẩu",
    "Truyền thông",
    "Bất động sản",
    "Giáo dục",
    "Du lịch",
    "Logistics",
)
_COMPANY_NAMES = (
    "Bình Minh",
    "Sao Việt",
    "An Phát",
    "Nhật Quang",
    "Thiên Long",
    "Đại Dương",
    "Phương Đông",
    "Trường Sơn",
    "Hoàng Hà",
    "Tân Phú",
    "Thái Bình",
    "Việt Hưng",
    "Kim Cương",
)


# --- Generator -------------------------------------------------------------
@dataclasses.dataclass
class _Address:
    street_no: int
    street: str
    district: str
    province: str

    def __str__(self) -> str:
        return f"Số {self.street_no} {self.street}, " f"{self.district}, {self.province}"


class VnFaker:
    """Vietnamese fake-data generator.

    Pass ``seed`` for deterministic output (test snapshots).
    """

    def __init__(self, seed: int | None = None):
        self._rng = random.Random(seed)

    # ---- name -----------------------------------------------------------
    def name(self, gender: str = "any") -> str:
        """Return a realistic Vietnamese full name (3 or 4 words)."""
        family = self._rng.choice(_FAMILY_NAMES)
        if gender == "male":
            middle = self._rng.choice(_MIDDLE_M)
            given = self._rng.choice(_GIVEN_M)
        elif gender == "female":
            middle = self._rng.choice(_MIDDLE_F)
            given = self._rng.choice(_GIVEN_F)
        else:
            if self._rng.random() < 0.5:
                middle = self._rng.choice(_MIDDLE_M)
                given = self._rng.choice(_GIVEN_M)
            else:
                middle = self._rng.choice(_MIDDLE_F)
                given = self._rng.choice(_GIVEN_F)
        return f"{family} {middle} {given}"

    # ---- phone ----------------------------------------------------------
    def phone(self, *, international: bool = False) -> str:
        """Vietnamese mobile number with valid prefix.

        ``international=True`` returns ``+84`` form.
        """
        prefix = self._rng.choice(_MOBILE_PREFIXES)
        rest = "".join(self._rng.choice("0123456789") for _ in range(7))
        local = f"{prefix}{rest}"
        if international:
            # Drop leading 0 and prepend +84
            return "+84" + local[1:]
        return f"{local[:4]}.{local[4:]}"  # "0xxx.xxxxxx" Vietnamese style

    # ---- address --------------------------------------------------------
    def address(self) -> str:
        prov = self._rng.choice(_PROVINCES)[1]
        dist = self._rng.choice(_DISTRICTS_BY_PROVINCE.get(prov, _DEFAULT_DISTRICTS))
        street = self._rng.choice(_STREET_NAMES)
        no = self._rng.randint(1, 999)
        return str(_Address(no, street, dist, prov))

    def province(self) -> str:
        return self._rng.choice(_PROVINCES)[1]

    # ---- ID -------------------------------------------------------------
    def cccd(self) -> str:
        """12-digit Vietnamese Citizen Identification Number.

        Layout: ``PPP G YY NNNNNN``
            PPP = province code (3 digits)
            G   = gender + century (1 digit, 0-3 = 1900s/2000s/etc)
            YY  = last 2 digits of birth year
            NNN = 6 random digits

        Output is the bare 12-digit string (no separators), matching the
        format on the back of the physical CCCD card.
        """
        prov = self._rng.choice(_PROVINCES)[0]
        # Gender + century: 0=M+1900s, 1=F+1900s, 2=M+2000s, 3=F+2000s
        gender_century = self._rng.choice("0123")
        if gender_century in "01":
            year = self._rng.randint(1950, 1999) % 100
        else:
            year = self._rng.randint(2000, 2009) % 100
        rest = "".join(self._rng.choice("0123456789") for _ in range(6))
        return f"{prov}{gender_century}{year:02d}{rest}"

    # ---- bank -----------------------------------------------------------
    def bank_account(self) -> str:
        prefix, length = self._rng.choice(_BANK_PREFIXES)
        digits = "".join(self._rng.choice("0123456789") for _ in range(length))
        return f"{prefix}-{digits}"

    # ---- money ----------------------------------------------------------
    def vnd_amount(
        self, min_amount: int = 10_000, max_amount: int = 100_000_000, round_to: int = 1_000
    ) -> str:
        """Returns Vietnamese-formatted price string e.g. ``1.500.000đ``."""
        if min_amount > max_amount:
            min_amount, max_amount = max_amount, min_amount
        v = self._rng.randint(min_amount, max_amount)
        v = (v // round_to) * round_to
        return self._format_vnd(v)

    @staticmethod
    def _format_vnd(amount: int) -> str:
        s = f"{amount:,}".replace(",", ".")
        return f"{s}đ"

    # ---- company -------------------------------------------------------
    def company(self) -> str:
        ctype = self._rng.choice(_COMPANY_TYPES)
        kind = self._rng.choice(_COMPANY_KINDS)
        name = self._rng.choice(_COMPANY_NAMES)
        return f"{ctype} {kind} {name}"

    # ---- email ---------------------------------------------------------
    def email(self, full_name: str | None = None) -> str:
        """Build a realistic VN email from a name or random."""
        name = full_name or self.name()
        # Strip diacritics roughly: take ASCII letters only, lowercase.
        ascii_parts = []
        for word in name.split():
            stripped = self._strip_diacritics(word).lower()
            ascii_parts.append(stripped)
        slug = ".".join(ascii_parts)
        suffix = "".join(self._rng.choice(string.digits) for _ in range(2))
        domain = self._rng.choice(("gmail.com", "yahoo.com", "outlook.com"))
        return f"{slug}{suffix}@{domain}"

    @staticmethod
    def _strip_diacritics(text: str) -> str:
        # Lightweight VN diacritic stripper — enough for emails.
        repl = {
            "à": "a",
            "á": "a",
            "ạ": "a",
            "ả": "a",
            "ã": "a",
            "â": "a",
            "ầ": "a",
            "ấ": "a",
            "ậ": "a",
            "ẩ": "a",
            "ẫ": "a",
            "ă": "a",
            "ằ": "a",
            "ắ": "a",
            "ặ": "a",
            "ẳ": "a",
            "ẵ": "a",
            "è": "e",
            "é": "e",
            "ẹ": "e",
            "ẻ": "e",
            "ẽ": "e",
            "ê": "e",
            "ề": "e",
            "ế": "e",
            "ệ": "e",
            "ể": "e",
            "ễ": "e",
            "ì": "i",
            "í": "i",
            "ị": "i",
            "ỉ": "i",
            "ĩ": "i",
            "ò": "o",
            "ó": "o",
            "ọ": "o",
            "ỏ": "o",
            "õ": "o",
            "ô": "o",
            "ồ": "o",
            "ố": "o",
            "ộ": "o",
            "ổ": "o",
            "ỗ": "o",
            "ơ": "o",
            "ờ": "o",
            "ớ": "o",
            "ợ": "o",
            "ở": "o",
            "ỡ": "o",
            "ù": "u",
            "ú": "u",
            "ụ": "u",
            "ủ": "u",
            "ũ": "u",
            "ư": "u",
            "ừ": "u",
            "ứ": "u",
            "ự": "u",
            "ử": "u",
            "ữ": "u",
            "ỳ": "y",
            "ý": "y",
            "ỵ": "y",
            "ỷ": "y",
            "ỹ": "y",
            "đ": "d",
        }
        out = []
        for ch in text:
            lower = ch.lower()
            mapped = repl.get(lower, ch)
            out.append(mapped if ch == lower else mapped.upper())
        return "".join(out)


__all__ = ["VnFaker"]
