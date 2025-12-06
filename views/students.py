import os
import io
import zipfile
import pandas as pd
import streamlit as st
from PIL import Image
from helpers import get_students_df, make_qr, make_barcode, get_user_filter


def render(collections):
    """Render students management page"""
    students_col = collections['students']

    st.title("👨‍🎓 Manage Students")

    with st.expander("➕ Add New Student"):
        st.subheader("Manual Entry")
        with st.form("add_student_manual"):
            sid = st.text_input("Student ID *", key="manual_student_id")
            name = st.text_input("Student Name *")
            course = st.text_input("Course")

            if st.form_submit_button("Add Student"):
                if not sid or not name:
                    st.error("Student ID and Name are required")
                else:
                    # Check for duplicate within user's own students only
                    user_filter = get_user_filter()
                    existing = students_col.find_one({"student_id": sid, **user_filter})
                    if existing:
                        st.warning("⚠️ Student ID already exists in your records")
                    else:
                        try:
                            students_col.insert_one({
                                "student_id": sid,
                                "name": name,
                                "course": course,
                                "qr_path": None,  # Generated on-the-fly
                                "barcode_path": None,  # Generated on-the-fly
                                "created_by": st.session_state.auth.get("username")
                            })
                            st.success(f"✅ Student {name} added successfully with QR code and barcode generated")
                        except Exception as e:
                            st.error(f"Error adding student: {e}")

        st.subheader("Add by QR/Barcode Scanner")
        st.info("💡 Use this option if you have a barcode/QR code scanner device connected to your computer.")
        with st.form("add_student_scanner"):
            st.markdown("**Instructions:**")
            st.markdown("- Click in the input field below")
            st.markdown("- Scan the student's QR code or barcode with your scanner device")
            st.markdown("- The code data will appear automatically")
            st.markdown("- Enter the student's name and course, then click 'Add Student' to save")

            scanner_code = st.text_input("Scan QR code or barcode here:",
                                       placeholder="Click here and scan with your scanner",
                                       key="scanner_input")
            if scanner_code:
                st.success(f"🔍 Code scanned: {scanner_code}")

            scanner_student_id = st.text_input("Student ID *", value=scanner_code if scanner_code else "",
                                             key="scanner_student_id", help="Auto-filled from scan or enter manually")
            scanner_student_name = st.text_input("Student Name *")
            scanner_course = st.text_input("Course")

            if st.form_submit_button("Add Student"):
                if not scanner_student_id or not scanner_student_name:
                    st.error("Student ID and Name are required")
                else:
                    # Check for duplicate within user's own students only
                    user_filter = get_user_filter()
                    existing = students_col.find_one({"student_id": scanner_student_id, **user_filter})
                    if existing:
                        st.warning("⚠️ Student ID already exists in your records")
                    else:
                        try:
                            students_col.insert_one({
                                "student_id": scanner_student_id,
                                "name": scanner_student_name,
                                "course": scanner_course,
                                "qr_path": None,
                                "barcode_path": None,
                                "created_by": st.session_state.auth.get("username")
                            })
                            st.success(f"✅ Student {scanner_student_name} added successfully with QR code and barcode generated")
                        except Exception as e:
                            st.error(f"Error adding student: {e}")

    st.subheader("📤 Bulk Upload CSV")
    st.info("CSV format: student_id, name, course (with headers)")

    uploaded_file = st.file_uploader("Choose CSV file", type=["csv"])
    if uploaded_file is not None:
        try:
            df = pd.read_csv(uploaded_file)
            st.dataframe(df)

            if st.button("Import Students from CSV"):
                inserted = skipped = 0
                for _, row in df.iterrows():
                    sid = str(row.get("student_id", "")).strip()
                    name = str(row.get("name", "")).strip()
                    course = str(row.get("course", "")).strip()

                    if not sid or not name:
                        continue

                    # Check for duplicate within user's own students only
                    user_filter = get_user_filter()
                    if students_col.find_one({"student_id": sid, **user_filter}):
                        skipped += 1
                        continue

                    try:
                        students_col.insert_one({
                            "student_id": sid,
                            "name": name,
                            "course": course,
                            "qr_path": None,
                            "barcode_path": None,
                            "created_by": st.session_state.auth.get("username")
                        })
                        inserted += 1
                    except Exception as e:
                        st.error(f"Error importing {sid}: {e}")

                st.success(f"✅ Imported {inserted} students, skipped {skipped} duplicates")
        except Exception as e:
            st.error(f"Error reading CSV: {e}")

    df_students = get_students_df(students_col)
    if not df_students.empty:
        st.subheader("📋 Current Students")
        st.dataframe(df_students[["student_id", "name", "course"]].sort_values(["course", "student_id"]))

        st.subheader("📥 Download Student Data")
        col1, col2 = st.columns(2)
        with col1:
            csv_data = df_students[["student_id", "name", "course"]].to_csv(index=False).encode()
            st.download_button(
                "📥 Download CSV",
                data=csv_data,
                file_name="students.csv",
                mime="text/csv"
            )

        with col2:
            mem = io.BytesIO()
            with pd.ExcelWriter(mem, engine="xlsxwriter") as writer:
                df_students[["student_id", "name", "course"]].to_excel(writer, index=False)
            mem.seek(0)
            st.download_button(
                "📊 Download Excel",
                data=mem,
                file_name="students.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

        st.subheader("🔍 View QR Codes and Barcodes")
        selected_student = st.selectbox(
            "Select Student",
            options=df_students["student_id"].tolist(),
            format_func=lambda x: f"{x} - {df_students[df_students['student_id']==x]['name'].iloc[0]}"
        )

        if selected_student:
            # Lookup student with user isolation
            user_filter = get_user_filter()
            student = students_col.find_one({"student_id": selected_student, **user_filter})
            col1, col2 = st.columns(2)
            
            from helpers import get_qr_image, get_barcode_image

            with col1:
                st.markdown("**QR Code:**")
                # Generate on the fly
                qr_img = get_qr_image(selected_student)
                
                # Convert to bytes for robust Streamlit display (Fixed TypeError)
                buf = io.BytesIO()
                qr_img.save(buf, format="PNG")
                byte_im = buf.getvalue()
                
                st.image(byte_im, width=200)
                
                # Use same buffer for download
                buf.seek(0)
                st.download_button("📥 Download QR", buf, file_name=f"{selected_student}_qr.png", mime="image/png")

            with col2:
                st.markdown("**Barcode:**")
                # Generate on the fly
                barcode_img_pil = get_barcode_image(selected_student)
                if barcode_img_pil:
                    # Convert to bytes for robust Streamlit display
                    buf = io.BytesIO()
                    barcode_img_pil.save(buf, format="PNG")
                    byte_im = buf.getvalue()
                    
                    st.image(byte_im, width=200)
                    
                    # Use same buffer for download
                    buf.seek(0)
                    st.download_button("📥 Download Barcode", buf, file_name=f"{selected_student}_barcode.png", mime="image/png")
                else:
                    st.warning("Barcode generation unavailable")

        st.subheader("📦 Download All QR Codes/Barcodes")
        if st.button("📦 Download All as ZIP"):
            zip_buffer = io.BytesIO()
            user_filter = get_user_filter()
            
            from helpers import get_qr_image, get_barcode_image
            
            with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zip_file:
                for _, student in df_students.iterrows():
                    sid = student["student_id"]
                    
                    # QR
                    qr_img = get_qr_image(sid)
                    qr_buf = io.BytesIO()
                    qr_img.save(qr_buf, format="PNG")
                    zip_file.writestr(f"{sid}_qr.png", qr_buf.getvalue())
                    
                    # Barcode
                    bc_img = get_barcode_image(sid)
                    if bc_img:
                        bc_buf = io.BytesIO()
                        bc_img.save(bc_buf, format="PNG")
                        zip_file.writestr(f"{sid}_barcode.png", bc_buf.getvalue())

            zip_buffer.seek(0)
            st.download_button(
                "📥 Download ZIP",
                data=zip_buffer,
                file_name="student_codes.zip",
                mime="application/zip"
            )
    else:
        st.info("📭 No students found. Add some students first.")
