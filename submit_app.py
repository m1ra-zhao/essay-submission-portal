
import os
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from supabase import create_client


# --------------------------------------------------
# 1. Configuration
# --------------------------------------------------

load_dotenv()


def get_setting(name):
    """Read Streamlit Cloud secrets or local environment variables."""
    try:
        value = st.secrets.get(name)
        if value:
            return str(value)
    except Exception:
        pass

    return os.getenv(name, "")


SUPABASE_URL = get_setting("SUPABASE_URL")

# Prefer the current publishable key. Support the legacy anon key too.
SUPABASE_KEY = (
    get_setting("SUPABASE_PUBLISHABLE_KEY")
    or get_setting("SUPABASE_ANON_KEY")
)

ESSAY_TYPES = [
    "Literary Analysis",
    "Textual Analysis",
    "Argumentative Essay",
    "Narrative Essay",
    "IB Paper 2 Comparative Essay",
    "Other",
]

CRITERION_FIELDS = {
    "understanding": "Understanding and Interpretation",
    "analysis": "Analysis and Evaluation",
    "organization": "Focus and Organization",
    "language": "Language",
}


def parse_optional_number(value, field_name):
    """Parse an optional non-negative number."""
    value = str(value).strip()

    if not value:
        return None

    try:
        number = float(value)
    except ValueError:
        raise ValueError(f"{field_name} must be a valid number.")

    if number < 0:
        raise ValueError(f"{field_name} cannot be negative.")

    return number


# --------------------------------------------------
# 2. Page configuration
# --------------------------------------------------

st.set_page_config(
    page_title="Essay Sample Submission",
    page_icon="📝",
    layout="centered",
)

st.title("Essay Sample Submission")
st.caption("Help improve a teacher-specific essay feedback tool.")

st.write(
    """
Submit an essay that has already been graded by your teacher.
If available, include the teacher's actual score, feedback, and
criterion scores. These details make the sample more useful.
"""
)

st.info(
    "Your submission will be private and reviewed by the site owner. "
    "It will not be automatically added to the grading library or "
    "displayed to other visitors."
)

if not SUPABASE_URL or not SUPABASE_KEY:
    st.warning(
        "The submission service is not configured yet. "
        "Please contact the site owner."
    )


# --------------------------------------------------
# 3. Optional TXT upload
# --------------------------------------------------

st.subheader("1. Essay Information")

st.session_state.setdefault("essay_body", "")

uploaded_file = st.file_uploader(
    "Upload an essay text file (.txt, optional)",
    type=["txt"],
    help="You can also paste the essay directly below.",
)

if uploaded_file is not None:
    file_bytes = uploaded_file.getvalue()

    signature = __import__("hashlib").sha256(file_bytes).hexdigest()

    if st.session_state.get("uploaded_signature") != signature:
        st.session_state["essay_body"] = file_bytes.decode(
            "utf-8-sig",
            errors="replace",
        )
        st.session_state["uploaded_signature"] = signature


# --------------------------------------------------
# 4. Submission form
# --------------------------------------------------

with st.form("essay_submission_form"):

    essay_title = st.text_input(
        "Essay Title *",
        max_chars=200,
        placeholder="e.g. Dry September - Literary Analysis",
    )

    essay_type = st.selectbox(
        "Essay Type *",
        ESSAY_TYPES,
    )

    assignment_prompt = st.text_area(
        "Assignment Prompt and Instructions",
        height=100,
        placeholder="Enter the original essay question...",
    )

    essay_text = st.text_area(
        "Essay Text *",
        key="essay_body",
        height=350,
        max_chars=20000,
        placeholder="Paste your essay here...",
    )

    st.caption(
        f"Essay length: {len(essay_text)} / 20,000 characters"
    )

    st.divider()
    st.subheader("2. Teacher's Assessment")

    st.caption(
        "Enter scores exactly as your teacher reported them. "
        "Leave a field blank if the information is unknown."
    )

    teacher_score_text = st.text_input(
        "Teacher's Reported Total Score",
        placeholder="Optional, e.g. 62",
    )

    teacher_max_text = st.text_input(
        "Maximum Score",
        placeholder="Optional — leave blank if unconfirmed",
    )

    criterion_scores = {}

    col1, col2 = st.columns(2)

    with col1:
        criterion_scores["understanding"] = st.text_input(
            "Understanding and Interpretation",
            placeholder="Score, if known",
        )

        criterion_scores["analysis"] = st.text_input(
            "Analysis and Evaluation",
            placeholder="Score, if known",
        )

    with col2:
        criterion_scores["organization"] = st.text_input(
            "Focus and Organization",
            placeholder="Score, if known",
        )

        criterion_scores["language"] = st.text_input(
            "Language",
            placeholder="Score, if known",
        )

    teacher_feedback = st.text_area(
        "Teacher's Overall Feedback",
        height=120,
        placeholder="Paste the teacher's original comments...",
    )

    paragraph_comments = st.text_area(
        "Paragraph-Level Comments",
        height=160,
        placeholder="Include specific comments on individual passages...",
    )

    rubric = st.text_area(
        "Grading Rubric and Additional Notes",
        height=120,
        placeholder="Optional: include the official criteria or other notes.",
    )

    st.divider()
    st.subheader("3. Privacy and Consent")

    consent = st.checkbox(
        "I confirm that this is my own work or that I have permission "
        "to share it. I consent to the site owner privately reviewing "
        "this submission and, if approved, using it as a reference "
        "sample for improving an essay feedback tool. I understand "
        "that the submission will not be publicly displayed. *"
    )

    submitted = st.form_submit_button(
        "Submit Essay Sample",
        type="primary",
        use_container_width=True,
    )


# --------------------------------------------------
# 5. Validate and submit
# --------------------------------------------------

if submitted:

    errors = []

    if not essay_title.strip():
        errors.append("Please enter an essay title.")

    if not essay_text.strip():
        errors.append("Please provide the essay text.")

    if len(essay_text) > 20000:
        errors.append("The essay cannot exceed 20,000 characters.")

    if not consent:
        errors.append("Consent is required before submitting.")

    try:
        parsed_score = parse_optional_number(
            teacher_score_text,
            "Teacher's reported total score",
        )

        parsed_maximum = parse_optional_number(
            teacher_max_text,
            "Maximum score",
        )

        parsed_criteria = {}

        for key, raw_value in criterion_scores.items():
            parsed = parse_optional_number(
                raw_value,
                CRITERION_FIELDS[key],
            )

            if parsed is not None:
                parsed_criteria[key] = parsed

    except ValueError as error:
        errors.append(str(error))
        parsed_score = None
        parsed_maximum = None
        parsed_criteria = {}

    if parsed_maximum is not None and parsed_maximum <= 0:
        errors.append(
            "Maximum score must be greater than zero, or left blank."
        )

    if (
        parsed_score is not None
        and parsed_maximum is not None
        and parsed_score > parsed_maximum
    ):
        errors.append(
            "The reported score cannot exceed the maximum score."
        )

    if not SUPABASE_URL or not SUPABASE_KEY:
        errors.append(
            "The submission service is not configured."
        )

    if errors:
        for error in errors:
            st.error(error)

    else:
        payload = {
            "status": "pending",
            "essay_title": essay_title.strip(),
            "essay_type": essay_type,
            "assignment_prompt": assignment_prompt.strip(),
            "essay_text": essay_text.strip(),
            "teacher_score": parsed_score,
            "teacher_max_score": parsed_maximum,
            "criterion_scores": parsed_criteria,
            "teacher_feedback": teacher_feedback.strip(),
            "paragraph_comments": paragraph_comments.strip(),
            "rubric": rubric.strip(),
            "consent": True,
        }

        try:
            supabase = create_client(
                SUPABASE_URL,
                SUPABASE_KEY,
            )

            # Insert without requesting the inserted row.
            supabase.table("submissions").insert(
                payload,
                returning="minimal",
            ).execute()

            st.success(
                "Your essay sample has been submitted successfully."
            )

            st.info(
                "Your submission is awaiting review. "
                "It has not automatically entered the grading library."
            )

            st.caption(
                "You may now close this page. Thank you for contributing."
            )

        except Exception:
            st.error(
                "Submission failed. Please try again later or "
                "contact the site owner."
            )
