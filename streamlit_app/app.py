from __future__ import annotations

import json
import os
from pathlib import Path

import requests
import streamlit as st


API_BASE_URL = os.getenv("TRF_API_BASE_URL", "http://localhost:8000")
API_USERNAME = os.getenv("TRF_UI_USERNAME", os.getenv("TRF_AUTH_USERNAME", "admin"))
API_PASSWORD = os.getenv("TRF_UI_PASSWORD", os.getenv("TRF_AUTH_PASSWORD", "changeme"))


def _csv_to_list(value: str) -> list[str]:
    return [item.strip() for item in value.split(",") if item.strip()]


def _none_if_blank(value: str) -> str | None:
    return value.strip() or None


def _normalize_form_payload(form_data: dict) -> dict:
    age_value = str(form_data["age"]).strip()
    return {
        "patient_name": _none_if_blank(form_data["patient_name"]),
        "patient_id": _none_if_blank(form_data["patient_id"]),
        "age": int(age_value) if age_value else None,
        "gender": _none_if_blank(form_data["gender"]),
        "doctor_name": _none_if_blank(form_data["doctor_name"]),
        "hospital_or_center_name": _none_if_blank(form_data["hospital_or_center_name"]),
        "requisition_date": _none_if_blank(form_data["requisition_date"]),
        "sample_type": _none_if_blank(form_data["sample_type"]),
        "test_names": _csv_to_list(form_data["test_names"]),
        "test_codes": _csv_to_list(form_data["test_codes"]),
        "priority": _none_if_blank(form_data["priority"]),
        "contact_number": _none_if_blank(form_data["contact_number"]),
        "notes": _none_if_blank(form_data["notes"]),
    }


def auth():
    return (API_USERNAME, API_PASSWORD)


def api_get(path: str):
    response = requests.get(f"{API_BASE_URL}{path}", auth=auth(), timeout=30)
    response.raise_for_status()
    return response


def api_post(path: str):
    response = requests.post(f"{API_BASE_URL}{path}", auth=auth(), timeout=30)
    response.raise_for_status()
    return response


def api_put(path: str, payload: dict):
    response = requests.put(f"{API_BASE_URL}{path}", json=payload, auth=auth(), timeout=30)
    response.raise_for_status()
    return response


def api_upload(uploaded_file):
    files = {
        "file": (
            uploaded_file.name,
            uploaded_file.getvalue(),
            uploaded_file.type or "application/octet-stream",
        )
    }
    response = requests.post(f"{API_BASE_URL}/trf/upload", files=files, auth=auth(), timeout=60)
    response.raise_for_status()
    return response


st.set_page_config(page_title="TRF Review Console", layout="wide")
st.title("TRF Review Console")
st.caption("FastAPI backend + Streamlit review workflow")

if "uploaded_this_session" not in st.session_state:
    st.session_state.uploaded_this_session = False
if "last_uploaded_document_id" not in st.session_state:
    st.session_state.last_uploaded_document_id = None

with st.sidebar:
    st.subheader("Upload TRF")
    uploaded_file = st.file_uploader("Choose a PDF or image", type=["pdf", "png", "jpg", "jpeg"])
    if uploaded_file and st.button("Upload and process", use_container_width=True):
        try:
            result = api_upload(uploaded_file).json()
            st.success(f"Processed document {result['document_id']}")
            st.session_state.uploaded_this_session = True
            st.session_state.last_uploaded_document_id = result["document_id"]
        except Exception as exc:
            st.error(str(exc))

st.subheader("Uploaded TRFs")

show_previous = st.toggle("Show previous documents", value=st.session_state.uploaded_this_session)
if not show_previous:
    st.info("Upload a TRF from the sidebar to begin.")
    st.stop()

try:
    documents = api_get("/trf").json()
except Exception as exc:
    st.error(f"Unable to load documents: {exc}")
    st.stop()

if not documents:
    st.info("No TRFs processed yet. Upload one from the sidebar to begin.")
    st.stop()

document_options = {
    f"{item['document_id']} | {item['source_file_name']} | {item['status']}": item["document_id"]
    for item in documents
}
labels = list(document_options)
default_index = 0
if st.session_state.last_uploaded_document_id:
    for idx, label in enumerate(labels):
        if document_options[label] == st.session_state.last_uploaded_document_id:
            default_index = idx
            break
selected_label = st.selectbox("Select document", labels, index=default_index)
document_id = document_options[selected_label]
document = api_get(f"/trf/{document_id}").json()

left_col, right_col = st.columns([1, 1])

with left_col:
    st.subheader("Document preview")
    try:
        file_response = api_get(f"/trf/{document_id}/file")
        content_type = file_response.headers.get("content-type", "")
        if "pdf" in content_type:
            st.download_button(
                "Download original PDF",
                data=file_response.content,
                file_name=document["source_file_name"],
                mime="application/pdf",
                use_container_width=True,
            )
        elif "image" in content_type:
            st.image(file_response.content, use_container_width=True)
        else:
            st.info("Preview unavailable for this file type.")
    except requests.HTTPError as exc:
        if exc.response is not None and exc.response.status_code == 404:
            st.info("Original uploaded file is not available for this record.")
        else:
            raise

    st.subheader("Validation")
    validation = document["validation"]
    st.write(f"Status: `{validation['status']}`")
    if validation["errors"]:
        st.error("\n".join(validation["errors"]))
    if validation["warnings"]:
        st.warning("\n".join(validation["warnings"]))

with right_col:
    st.subheader("Review and correct")
    extracted = document["extracted_data"]
    form_data = {}
    with st.form("correction_form"):
        form_data["patient_name"] = st.text_input("Patient name", extracted.get("patient_name") or "")
        form_data["patient_id"] = st.text_input("Patient ID", extracted.get("patient_id") or "")
        form_data["age"] = st.text_input("Age", str(extracted.get("age") or ""))
        form_data["gender"] = st.text_input("Gender", extracted.get("gender") or "")
        form_data["doctor_name"] = st.text_input("Doctor name", extracted.get("doctor_name") or "")
        form_data["hospital_or_center_name"] = st.text_input(
            "Hospital / center",
            extracted.get("hospital_or_center_name") or "",
        )
        form_data["requisition_date"] = st.text_input("Requisition date", extracted.get("requisition_date") or "")
        form_data["sample_type"] = st.text_input("Sample type", extracted.get("sample_type") or "")
        form_data["test_names"] = st.text_area(
            "Test names (comma separated)",
            ", ".join(extracted.get("test_names") or []),
        )
        form_data["test_codes"] = st.text_area(
            "Test codes (comma separated)",
            ", ".join(extracted.get("test_codes") or []),
        )
        form_data["priority"] = st.text_input("Priority", extracted.get("priority") or "")
        form_data["contact_number"] = st.text_input("Contact number", extracted.get("contact_number") or "")
        form_data["notes"] = st.text_area("Notes", extracted.get("notes") or "")
        save_clicked = st.form_submit_button("Save corrected version")

    if save_clicked:
        payload = {"extracted_data": _normalize_form_payload(form_data)}
        try:
            document = api_put(f"/trf/{document_id}/correct", payload).json()
            st.success("Corrected version saved")
        except Exception as exc:
            st.error(str(exc))

    action_col_1, action_col_2 = st.columns(2)
    with action_col_1:
        if st.button("Re-run validation", use_container_width=True):
            try:
                result = api_post(f"/trf/{document_id}/validate").json()
                st.success(f"Validation status: {result['status']}")
            except Exception as exc:
                st.error(str(exc))
    with action_col_2:
        if st.button("Approve", use_container_width=True):
            try:
                document = api_post(f"/trf/{document_id}/approve").json()
                st.success(f"Document {document['document_id']} approved")
            except Exception as exc:
                st.error(str(exc))

st.subheader("Normalized JSON")
visible_document = dict(document)
visible_document.pop("extraction_provider", None)
visible_document.pop("extraction_model", None)
st.code(json.dumps(visible_document, indent=2), language="json")
if document.get("extraction_note"):
    st.info(document["extraction_note"])
