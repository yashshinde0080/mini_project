from datetime import date, datetime
import streamlit as st
from PIL import Image
from helpers import decode_from_camera, mark_attendance, get_user_filter


def render(collections):
    """Render QR/Barcode scanning page"""
    students_col = collections['students']
    att_col = collections['attendance']
    use_mongo = collections['use_mongo']

    st.title("📷 Scan QR Code or Barcode for Attendance")

    chosen_date = st.date_input("Select Date", value=date.today())
    st.info("📱 Scan a student's QR code or barcode using the camera or a hardware scanner")

    # Initialize session state for scanned data
    if "last_scanned_code" not in st.session_state:
        st.session_state.last_scanned_code = None
    if "last_scanned_student" not in st.session_state:
        st.session_state.last_scanned_student = None

    scan_method = st.radio("Choose scanning method:",
                          ["📷 Camera", "⌨️ Manual Barcode Scanner"])

    if scan_method == "📷 Camera":
        camera_image = st.camera_input("Take a photo of QR code or barcode")

        if camera_image is not None:
            try:
                img = Image.open(camera_image)
                st.image(img, caption="Captured Image", width=300)

                with st.spinner("Decoding QR code/barcode..."):
                    code_data, code_type = decode_from_camera(img)

                if code_data:
                    st.success(f"🔍 {code_type} detected: **{code_data}**")

                    # Lookup student with user isolation
                    user_filter = get_user_filter()
                    student = students_col.find_one({"student_id": code_data, **user_filter})

                    if not student:
                        st.error("❌ Student not found in your records")
                        st.session_state.last_scanned_code = None
                        st.session_state.last_scanned_student = None
                    else:
                        # Store scanned data in session state
                        st.session_state.last_scanned_code = code_data
                        st.session_state.last_scanned_student = student

                        st.info(f"👤 Student: **{student.get('name', code_data)}** | Course: {student.get('course', 'N/A')}")

                        # Confirmation button to mark attendance
                        if st.button("✅ Confirm & Mark Attendance", type="primary", key="confirm_camera"):
                            combined_datetime = datetime.combine(chosen_date, datetime.now().time())
                            result = mark_attendance(
                                att_col,
                                use_mongo,
                                code_data,
                                1,
                                combined_datetime,
                                course=student.get("course"),
                                method="camera_scan"
                            )

                            if "error" in result and result["error"] == "already":
                                st.warning(f"⚠️ Attendance already marked for {student.get('name', code_data)} on {chosen_date}")
                            else:
                                st.success(f"✅ Marked {student.get('name', code_data)} as PRESENT for {chosen_date}")
                                st.balloons()
                                # Clear the scanned data
                                st.session_state.last_scanned_code = None
                                st.session_state.last_scanned_student = None
                else:
                    st.warning("❌ No QR code or barcode detected in the image. Please try again.")
                    st.session_state.last_scanned_code = None
                    st.session_state.last_scanned_student = None

            except Exception as e:
                st.error(f"Error processing image: {str(e)}")

    elif scan_method == "⌨️ Manual Barcode Scanner":
        st.info("💡 Use this option if you have a barcode scanner device connected to your computer.")
        st.markdown("**Instructions:**")
        st.markdown("- Click in the input field below")
        st.markdown("- Scan the student's QR code or barcode with your scanner device")
        st.markdown("- The code data will appear automatically")
        st.markdown("- Click 'Mark Attendance' to save")

        with st.form("barcode_scanner"):
            scanned_code = st.text_input("Scan QR code or barcode here:",
                                       placeholder="Click here and scan with your scanner")

            if st.form_submit_button("✅ Mark Attendance"):
                if not scanned_code:
                    st.error("Please scan a QR code or barcode first")
                else:
                    # Lookup student with user isolation
                    user_filter = get_user_filter()
                    student = students_col.find_one({"student_id": scanned_code, **user_filter})
                    if not student:
                        st.error("❌ Student not found in your records")
                    else:
                        combined_datetime = datetime.combine(chosen_date, datetime.now().time())
                        result = mark_attendance(
                            att_col,
                            use_mongo,
                            scanned_code,
                            1,
                            combined_datetime,
                            course=student.get("course"),
                            method="scanner_device"
                        )

                        if "error" in result and result["error"] == "already":
                            st.warning(f"⚠️ Attendance already marked for {student.get('name', scanned_code)} on {chosen_date}")
                        else:
                            st.success(f"✅ Marked {student.get('name', scanned_code)} as PRESENT for {chosen_date}")
