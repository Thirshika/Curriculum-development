import hashlib
import re
from decimal import Decimal

import pymupdf

RULE_VALUE = re.compile(r"(?P<value>\d+(?:\.\d+)?)\s*(?:academic\s+)?credits?\b", re.IGNORECASE)
SEMESTER = re.compile(r"\bsemester\s*(\d{1,2})\b", re.IGNORECASE)
CLAUSE = re.compile(r"\b(?:section|clause|regulation|rule)\s*[\d.]+", re.IGNORECASE)
CATEGORY_NAMES = (
    "Basic Science",
    "Engineering Science",
    "Humanities",
    "Professional Core",
    "Open Elective",
    "Elective",
    "Project",
    "Internship",
    "Major",
    "Minor",
    "Multidisciplinary",
    "Ability Enhancement",
    "Value-Added",
    "Summer Internship",
    "Research Project",
    "Research",
    "Vocational",
    "Skill-Based",
    "Discipline-Specific",
    "Core",
)
GENERIC_CATEGORY_NAMES = {"different types of", "types of", "various", "relevant"}
COURSE_CODE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,31}$")
DECIMAL_VALUE = re.compile(r"^\d+(?:\.\d+)?$")
LTP_VALUE = re.compile(
    r"^\s*(\d+(?:\.\d+)?)\s*[-–—/]\s*(\d+(?:\.\d+)?)\s*[-–—/]\s*(\d+(?:\.\d+)?)\s*$"
)
ROMAN_SEMESTERS = {
    "i": 1,
    "ii": 2,
    "iii": 3,
    "iv": 4,
    "v": 5,
    "vi": 6,
    "vii": 7,
    "viii": 8,
    "ix": 9,
    "x": 10,
    "xi": 11,
    "xii": 12,
}


def extract_pdf_pages(content: bytes) -> list[str]:
    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            if document.is_encrypted or document.page_count < 1:
                raise ValueError("The PDF is encrypted or has no pages.")
            return [page.get_text("text") for page in document]
    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise ValueError("The uploaded file is not a readable PDF.") from exc


def _category_for(text: str) -> str | None:
    lowered = text.casefold()
    for category in sorted(CATEGORY_NAMES, key=len, reverse=True):
        if re.search(rf"\b{re.escape(category.casefold())}\b", lowered):
            return category
    match = re.search(
        r"\b(?:in|for|under)\s+(?:the\s+)?([A-Za-z][A-Za-z0-9/& -]{1,50}?)\s+(?:category|courses?)\b",
        text,
        re.IGNORECASE,
    )
    category = match.group(1).strip(" .,:;") if match else None
    return None if category and category.casefold() in GENERIC_CATEGORY_NAMES else category


def _bound(text: str) -> str:
    lowered = text.casefold()
    if re.search(r"\b(minimum|min\.?|at least|not less than)\b", lowered):
        return "minimum"
    if re.search(r"\b(maximum|max\.?|at most|not more than|not exceed)\b", lowered):
        return "maximum"
    return "total"


def extract_credit_rules(pages: list[str]) -> list[dict]:
    rules: list[dict] = []
    for page_number, page_text in enumerate(pages, start=1):
        for line in re.split(r"(?<=[.;])\s+|\n+", page_text):
            text = " ".join(line.split()).strip()
            if not text or not re.search(r"\bcredits?\b", text, re.IGNORECASE):
                continue
            number = RULE_VALUE.search(text)
            if number is None:
                continue
            category = _category_for(text)
            semester_match = SEMESTER.search(text)
            semester = int(semester_match.group(1)) if semester_match else None
            bound = _bound(text)
            if category:
                rule_type = (
                    "category_min"
                    if bound == "minimum"
                    else "category_max"
                    if bound == "maximum"
                    else "category_total"
                )
            elif semester is not None:
                rule_type = "semester_min" if bound == "minimum" else "semester_max" if bound == "maximum" else "semester_total"
            elif re.search(r"\b(total|programme|program|degree)\b", text, re.IGNORECASE) or bound in {"minimum", "maximum"}:
                rule_type = "total_min" if bound == "minimum" else "total_max" if bound == "maximum" else "other"
            else:
                rule_type = "other"
            clause_match = CLAUSE.search(text)
            rules.append(
                {
                    "text": text[:4000],
                    "page_number": page_number,
                    "clause": clause_match.group(0) if clause_match else None,
                    "rule_type": rule_type,
                    "category": category,
                    "semester": semester,
                    "value": Decimal(number.group("value")) if number and rule_type != "other" else None,
                }
            )
    return rules


def _credit_requirement_columns(rows: list[list[str | None]]) -> tuple[int, int] | None:
    for header_end in range(min(3, len(rows))):
        column_count = max((len(row) for row in rows[: header_end + 1]), default=0)
        headers = [
            " ".join(
                " ".join((rows[row_index][column] or "").split())
                for row_index in range(header_end + 1)
                if column < len(rows[row_index]) and rows[row_index][column]
            ).casefold()
            for column in range(column_count)
        ]
        category_index = next(
            (index for index, value in enumerate(headers) if "category of course" in value or "broad category" in value),
            None,
        )
        combined_headers = re.sub(r"\s+", "", "".join(headers))
        requirement_index = next(
            (
                index
                for index, value in enumerate(headers)
                if "minimum" in value or "credit" in value or "requirement" in value
            ),
            None,
        )
        has_minimum_requirement = (
            "minimumcreditrequirement" in combined_headers
            or "minimumcreditrequirements" in combined_headers
        )
        if category_index is not None and requirement_index is not None and has_minimum_requirement:
            return category_index, header_end
    return None


def _credit_range(value: str | None) -> tuple[Decimal, Decimal] | None:
    text = " ".join((value or "").split()).replace("−", "-").replace("�", "-")
    values = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(?:-|–|—|to)\s*(\d+(?:\.\d+)?)", text, re.IGNORECASE)
    if values:
        lower, upper = Decimal(values.group(1)), Decimal(values.group(2))
        return (min(lower, upper), max(lower, upper))
    single = _cell_decimal(text)
    return (single, single) if single is not None else None


def _credit_category(value: str) -> str | None:
    normalized = " ".join(value.split()).strip(" .:")
    lowered = normalized.casefold()
    if lowered.startswith("total"):
        return "total"
    if "major" in lowered:
        return "Major"
    if "minor" in lowered:
        return "Minor"
    if "multidisciplinary" in lowered or "inter-disciplinary" in lowered or "interdisciplinary" in lowered:
        return "Multidisciplinary"
    if "ability enhancement" in lowered:
        return "Ability Enhancement"
    if "skill enhancement" in lowered or "skill-based" in lowered:
        return "Skill-Based"
    if "value added" in lowered or "value-added" in lowered:
        return "Value-Added"
    if "summer internship" in lowered:
        return "Summer Internship"
    if "research project" in lowered or "dissertation" in lowered:
        return "Research Project"
    return None


def extract_credit_table_rules(content: bytes) -> list[dict]:
    rules: list[dict] = []
    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            continuing_credit_table = False
            for page_number, page in enumerate(document, start=1):
                tables = page.find_tables().tables
                current_page_has_header = False
                for table in tables:
                    rows = table.extract()
                    header = _credit_requirement_columns(rows)
                    if header:
                        category_index, header_end = header
                        first_data_row = header_end + 1
                        current_page_has_header = True
                    elif continuing_credit_table:
                        category_index, first_data_row = 1, 0
                    else:
                        continue

                    for row in rows[first_data_row:]:
                        category_text = (
                            " ".join((row[category_index] or "").split()).strip()
                            if category_index < len(row)
                            else ""
                        )
                        category = _credit_category(category_text)
                        if category is None:
                            continue
                        values = [
                            " ".join((value or "").split()).strip()
                            for value in row[category_index + 1 :]
                            if value and value.strip()
                        ][:2]
                        for duration, raw_value in zip((3, 4), values):
                            if category == "total":
                                total_value = _cell_decimal(raw_value)
                                rules.append(
                                    {
                                        "text": (
                                            f"Total minimum credit requirement: {raw_value} credits."
                                        ),
                                        "page_number": page_number,
                                        "clause": "Credit requirement table",
                                        "rule_type": "total_min",
                                        "category": None,
                                        "semester": None,
                                        "programme_duration_years": duration,
                                        "value": total_value,
                                    }
                                )
                                continue
                            credit_range = _credit_range(raw_value)
                            value = credit_range[0] if credit_range else None
                            display_value = (
                                f"{credit_range[0]:g}–{credit_range[1]:g}"
                                if credit_range and credit_range[0] != credit_range[1]
                                else raw_value
                            )
                            rules.append(
                                {
                                    "text": (
                                        f"Broad category of course: {category_text}; "
                                        f"minimum credit requirement: {display_value} credits."
                                    ),
                                    "page_number": page_number,
                                    "clause": "Credit requirement table",
                                    "rule_type": "category_min",
                                    "category": category,
                                    "semester": None,
                                    "programme_duration_years": duration,
                                    "value": value,
                                }
                            )
                            if credit_range and credit_range[1] != credit_range[0]:
                                rules.append(
                                    {
                                        "text": (
                                            f"Broad category of course: {category_text}; "
                                            f"minimum credit requirement: {display_value} credits."
                                        ),
                                        "page_number": page_number,
                                        "clause": "Credit requirement table",
                                        "rule_type": "category_max",
                                        "category": category,
                                        "semester": None,
                                        "programme_duration_years": duration,
                                        "value": credit_range[1],
                                    }
                                )
                continuing_credit_table = current_page_has_header
    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise ValueError("The uploaded file is not a readable PDF.") from exc
    return rules


def _course_table_headers(rows: list[list[str | None]]) -> tuple[dict[str, int], int] | None:
    best: tuple[dict[str, int], int, int] | None = None
    for start in range(min(3, len(rows))):
        for end in range(start, min(start + 3, len(rows))):
            column_count = max((len(row) for row in rows[start : end + 1]), default=0)
            headers = [
                " ".join(
                    " ".join((rows[row_index][column] or "").split())
                    for row_index in range(start, end + 1)
                    if column < len(rows[row_index]) and rows[row_index][column]
                ).casefold()
                for column in range(column_count)
            ]
            code_index = next(
                (index for index, value in enumerate(headers) if re.search(r"\b(?:course|subject|paper)\s*(?:code|no\.?|number)\b", value)),
                None,
            )
            name_index = next(
                (index for index, value in enumerate(headers) if re.search(r"\b(?:course|subject)\s*(?:title|name)\b", value)),
                None,
            )
            if name_index is None:
                name_index = next(
                    (index for index, value in enumerate(headers) if value.strip() in {"course", "subject"}),
                    None,
                )
            category_index = next(
                (index for index, value in enumerate(headers) if re.search(r"\bcategory\b", value)),
                None,
            )
            semester_index = next(
                (index for index, value in enumerate(headers) if re.search(r"\b(?:semester|sem\.?)\b", value)),
                None,
            )
            credits_index = next(
                (
                    index
                    for index, value in enumerate(headers)
                    if re.search(r"\bcredits?\b", value)
                    and not re.search(r"\b(?:credit\s+points?|minimum\s+credit\s+requirement)\b", value)
                ),
                None,
            )
            ltp_index = next(
                (
                    index
                    for index, value in enumerate(headers)
                    if re.search(r"\bl\s*[-–—/]\s*t\s*[-–—/]\s*p\b", value)
                    or all(word in value for word in ("lecture", "tutorial", "practical"))
                ),
                None,
            )
            separate_hours = {
                "lecture_hours": next((index for index, value in enumerate(headers) if value.strip() in {"l", "lec", "lecture", "lecture hours"}), None),
                "tutorial_hours": next((index for index, value in enumerate(headers) if value.strip() in {"t", "tut", "tutorial", "tutorial hours"}), None),
                "practical_hours": next((index for index, value in enumerate(headers) if value.strip() in {"p", "prac", "practical", "practical hours"}), None),
            }
            if None in {name_index, category_index, semester_index, credits_index}:
                continue
            if ltp_index is None and any(index is None for index in separate_hours.values()):
                continue
            found = {
                "name": name_index,
                "category": category_index,
                "semester": semester_index,
                "credits": credits_index,
                **({"course_code": code_index} if code_index is not None else {}),
                **({"ltp": ltp_index} if ltp_index is not None else separate_hours),
            }
            score = len(found)
            if best is None or score > len(best[0]) or (score == len(best[0]) and end < best[1]):
                best = (found, end, score)
    return (best[0], best[1]) if best else None


def _cell_decimal(value: str | None) -> Decimal | None:
    text = " ".join((value or "").split())
    return Decimal(text) if DECIMAL_VALUE.fullmatch(text) else None


def _semester_number(value: str | None) -> int | None:
    text = " ".join((value or "").split()).strip().casefold()
    if text.isdecimal():
        number = int(text)
        return number if 1 <= number <= 24 else None
    return ROMAN_SEMESTERS.get(text)


def _generated_course_code(name: str, category: str, semester: int) -> str:
    source = f"{name.casefold()}|{category.casefold()}|{semester}".encode("utf-8")
    return f"AUTO{hashlib.sha256(source).hexdigest()[:20].upper()}"


def extract_courses_from_pdf(content: bytes) -> list[dict]:
    courses: list[dict] = []
    seen_codes: set[str] = set()
    try:
        with pymupdf.open(stream=content, filetype="pdf") as document:
            for page in document:
                for table in page.find_tables().tables:
                    rows = table.extract()
                    header = _course_table_headers(rows)
                    if header is None:
                        continue
                    columns, header_end = header
                    previous_category: str | None = None
                    previous_semester: int | None = None
                    for row in rows[header_end + 1 :]:
                        def cell(name: str) -> str:
                            index = columns.get(name)
                            return " ".join((row[index] or "").split()).strip() if index is not None and index < len(row) else ""

                        name = cell("name")
                        category = cell("category") or previous_category
                        semester = _semester_number(cell("semester")) or previous_semester
                        if category:
                            previous_category = category
                        if semester:
                            previous_semester = semester
                        credits = _cell_decimal(cell("credits"))
                        if (
                            len(name) < 3
                            or len(name) > 200
                            or re.fullmatch(r"(?:course|subject)\s+\d+", name, re.IGNORECASE)
                            or not category
                            or len(category) > 100
                            or semester is None
                            or credits is None
                            or credits <= 0
                        ):
                            continue

                        if "ltp" in columns:
                            ltp = LTP_VALUE.fullmatch(cell("ltp"))
                            if ltp is None:
                                continue
                            lecture_hours, tutorial_hours, practical_hours = (
                                Decimal(value) for value in ltp.groups()
                            )
                        else:
                            hours = {
                                field: _cell_decimal(cell(field))
                                for field in ("lecture_hours", "tutorial_hours", "practical_hours")
                            }
                            if any(value is None for value in hours.values()):
                                continue
                            lecture_hours = hours["lecture_hours"]
                            tutorial_hours = hours["tutorial_hours"]
                            practical_hours = hours["practical_hours"]

                        course_code = cell("course_code").upper()
                        if not COURSE_CODE.fullmatch(course_code):
                            course_code = _generated_course_code(name, category, semester)
                        if course_code.casefold() in seen_codes:
                            continue
                        seen_codes.add(course_code.casefold())
                        courses.append(
                            {
                                "course_code": course_code,
                                "name": name,
                                "category": category,
                                "semester": semester,
                                "lecture_hours": lecture_hours,
                                "tutorial_hours": tutorial_hours,
                                "practical_hours": practical_hours,
                                "credits": credits,
                            }
                        )
    except (pymupdf.FileDataError, pymupdf.EmptyFileError) as exc:
        raise ValueError("The uploaded file is not a readable PDF.") from exc
    return courses
