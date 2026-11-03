import textwrap
from io import BytesIO

import pymupdf
from docx import Document
from docx.shared import Inches, Pt


def _curriculum_lines(content: dict) -> list[tuple[str, bool]]:
    lines: list[tuple[str, bool]] = []

    def heading(value: str) -> None:
        lines.append((value, True))
        lines.append(("", False))

    def paragraph(value: str) -> None:
        lines.append((value, False))

    heading("Programme overview")
    paragraph(str(content["programme_overview"]))

    heading("Programme educational objectives")
    for index, objective in enumerate(content["programme_educational_objectives"], start=1):
        paragraph(f"{index}. {objective}")

    for title, key in (
        ("Programme outcomes", "programme_outcomes"),
        ("Programme-specific outcomes", "programme_specific_outcomes"),
    ):
        heading(title)
        for outcome in content[key]:
            paragraph(f"{outcome['code']}: {outcome['statement']}")

    heading("Semester-wise curriculum")
    for semester in content["semesters"]:
        heading(f"Semester {semester['semester_number']}: {semester['title']}")
        for course in semester["courses"]:
            heading(f"{course['course_code']} — {course['title']} ({course['credits']} credits)")
            paragraph(f"Category: {course['category']}")
            paragraph(course["description"])
            for label, key in (
                ("Learning objectives", "learning_objectives"),
                ("Course outcomes", "course_outcomes"),
                ("Syllabus units", "units"),
                ("Teaching methods", "teaching_methods"),
                ("Assessment methods", "assessment_methods"),
                ("Learning resources", "learning_resources"),
            ):
                paragraph(f"{label}:")
                values = course[key]
                if key == "course_outcomes":
                    for item in values:
                        paragraph(f"  {item['code']}: {item['statement']}")
                elif key == "units":
                    for item in values:
                        paragraph(
                            f"  Unit {item['unit_number']}: {item['title']} — {', '.join(item['topics'])}"
                        )
                else:
                    for item in values:
                        paragraph(f"  • {item}")

    heading("Credit distribution")
    for allocation in content["credit_distribution"]:
        paragraph(f"Semester {allocation['semester_number']}: {allocation['credits']} credits")

    for title, key in (("CO–PO mapping", "co_po_mapping"), ("CO–PSO mapping", "co_pso_mapping")):
        heading(title)
        for mapping in content[key]:
            paragraph(
                f"{mapping['course_code']} {mapping['course_outcome_code']} → "
                f"{', '.join(mapping['programme_outcome_codes'])}"
            )

    return lines


def render_curriculum_docx(
    *,
    title: str,
    university: str,
    programme: str,
    academic_year: str,
    version_number: int,
    content: dict,
) -> bytes:
    document = Document()
    section = document.sections[0]
    section.top_margin = Inches(0.7)
    section.bottom_margin = Inches(0.7)
    document.add_heading(title, level=0)
    metadata = document.add_paragraph()
    metadata.add_run(f"{university} | {programme} | Academic year {academic_year} | Version {version_number}")
    document.add_paragraph("Admin-prepared curriculum document.")
    for text, is_heading in _curriculum_lines(content):
        if not text:
            continue
        if is_heading:
            document.add_heading(text, level=2)
        else:
            document.add_paragraph(text)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def render_curriculum_pdf(
    *,
    title: str,
    university: str,
    programme: str,
    academic_year: str,
    version_number: int,
    content: dict,
) -> bytes:
    document = pymupdf.open()
    page_width, page_height = 595, 842
    margin_x, margin_y = 50, 48
    font_size = 10
    line_height = 14
    page = document.new_page(width=page_width, height=page_height)
    y = margin_y

    def new_page() -> None:
        nonlocal page, y
        page = document.new_page(width=page_width, height=page_height)
        y = margin_y

    def write_line(value: str, is_heading: bool = False) -> None:
        nonlocal y
        if not value:
            y += line_height / 2
            return
        value = value.encode("ascii", "replace").decode("ascii")
        size = 14 if is_heading else font_size
        left = margin_x + (0 if is_heading else 4)
        available_chars = max(30, int((page_width - left - margin_x) / (size * 0.52)))
        wrapped = textwrap.wrap(value, width=available_chars, replace_whitespace=False) or [""]
        for part in wrapped:
            if y + line_height > page_height - margin_y:
                new_page()
            page.insert_text((left, y), part, fontsize=size, fontname="helv")
            y += line_height + (2 if is_heading else 0)

    write_line(title, True)
    write_line(f"{university} | {programme} | Academic year {academic_year} | Version {version_number}")
    write_line("Admin-prepared curriculum document.")
    write_line("")
    for value, is_heading in _curriculum_lines(content):
        write_line(value, is_heading)
    result = document.tobytes()
    document.close()
    return result
