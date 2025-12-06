import streamlit as st
from helpers import require_reauth, get_user_filter, is_admin


def render(collections, user_manager):
    """Render settings page"""
    require_reauth("settings", user_manager)

    st.title("⚙️ Settings")

    # -------------------- Change Password Section --------------------
    st.subheader("🔒 Change Password")
    with st.form("change_password"):
        current_password = st.text_input("Current Password", type="password")
        new_password = st.text_input("New Password", type="password")
        confirm_password = st.text_input("Confirm New Password", type="password")

        if st.form_submit_button("Change Password"):
            if not current_password or not new_password:
                st.error("All fields are required")
            elif new_password != confirm_password:
                st.error("New passwords do not match")
            else:
                success, message = user_manager.change_password(
                    st.session_state.auth['username'],
                    current_password,
                    new_password
                )
                if success:
                    st.success(message)
                else:
                    st.error(message)

    st.divider()

    # -------------------- Teacher Management Section (Admin Only) --------------------
    if is_admin():
        st.subheader("👨‍🏫 Teacher Management")

        tab1, tab2 = st.tabs(["➕ Add Teacher", "🗑️ Delete Teacher"])

        with tab1:
            st.markdown("**Add a new teacher account**")
            with st.form("add_teacher"):
                col1, col2 = st.columns(2)
                with col1:
                    new_username = st.text_input("Username*", placeholder="e.g., john_doe")
                    new_email = st.text_input("Email*", placeholder="e.g., john@school.edu")
                with col2:
                    new_name = st.text_input("Full Name*", placeholder="e.g., John Doe")
                    new_password = st.text_input("Password*", type="password",
                                                  help="Min 8 chars, 1 uppercase, 1 lowercase, 1 number, 1 special char")

                if st.form_submit_button("➕ Add Teacher", type="primary"):
                    if not all([new_username, new_email, new_name, new_password]):
                        st.error("All fields are required")
                    else:
                        success, message = user_manager.create_user(
                            username=new_username,
                            password=new_password,
                            email=new_email,
                            name=new_name,
                            role="teacher"
                        )
                        if success:
                            st.success(f"✅ Teacher '{new_name}' added successfully!")
                            st.rerun()
                        else:
                            st.error(f"❌ {message}")

        with tab2:
            st.markdown("**Delete an existing teacher account**")
            st.warning("⚠️ Deleting a teacher will NOT delete their students or attendance records.")

            # Get all teachers (exclude admin)
            teachers = list(user_manager.users_col.find({"role": "teacher"}))

            if not teachers:
                st.info("No teachers found in the system.")
            else:
                # Create a list of teacher options
                teacher_options = {f"{t.get('name', 'Unknown')} (@{t.get('username')}) - {t.get('email', 'No email')}": t.get('username') for t in teachers}

                selected_teacher = st.selectbox(
                    "Select Teacher to Delete",
                    options=list(teacher_options.keys()),
                    index=None,
                    placeholder="Choose a teacher..."
                )

                if selected_teacher:
                    teacher_username = teacher_options[selected_teacher]

                    # Confirmation
                    st.error(f"⚠️ You are about to delete: **{selected_teacher}**")
                    confirm_text = st.text_input(
                        f"Type '{teacher_username}' to confirm deletion:",
                        placeholder=f"Type {teacher_username}"
                    )

                    if st.button("🗑️ Delete Teacher", type="primary"):
                        if confirm_text == teacher_username:
                            try:
                                user_manager.users_col.delete_one({"username": teacher_username})
                                st.success(f"✅ Teacher '{teacher_username}' deleted successfully!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"❌ Error deleting teacher: {str(e)}")
                        else:
                            st.error("❌ Confirmation text doesn't match. Please type the username exactly.")

        st.divider()

    # -------------------- Delete Students Section --------------------
    st.subheader("🗑️ Delete Students")

    user_filter = get_user_filter()
    students = list(collections['students'].find(user_filter))

    if not students:
        st.info("No students found in your records.")
    else:
        st.warning("⚠️ Deleting a student will also delete all their attendance records.")

        # Create tabs for single and bulk delete
        del_tab1, del_tab2 = st.tabs(["🎯 Delete Single Student", "📋 Bulk Delete Students"])

        with del_tab1:
            # Create student options
            student_options = {f"{s.get('name', 'Unknown')} ({s.get('student_id')}) - {s.get('course', 'No course')}": s.get('student_id') for s in students}

            selected_student = st.selectbox(
                "Select Student to Delete",
                options=list(student_options.keys()),
                index=None,
                placeholder="Choose a student...",
                key="single_delete_student"
            )

            if selected_student:
                student_id = student_options[selected_student]

                # Show student details
                student = collections['students'].find_one({"student_id": student_id, **user_filter})
                if student:
                    st.markdown(f"""
                    **Student Details:**
                    - **ID:** {student.get('student_id')}
                    - **Name:** {student.get('name', 'N/A')}
                    - **Course:** {student.get('course', 'N/A')}
                    """)

                    # Count attendance records
                    att_count = collections['attendance'].count_documents({"student_id": student_id, **user_filter})
                    st.info(f"📝 This student has **{att_count}** attendance records that will also be deleted.")

                # Confirmation
                confirm_delete = st.checkbox(f"I confirm I want to delete '{student.get('name', student_id)}'", key="confirm_single_delete")

                if st.button("🗑️ Delete Student", type="primary", disabled=not confirm_delete, key="btn_single_delete"):
                    try:
                        # Delete student
                        collections['students'].delete_one({"student_id": student_id, **user_filter})
                        # Delete attendance records
                        deleted_att = collections['attendance'].delete_many({"student_id": student_id, **user_filter})

                        st.success(f"✅ Student '{student.get('name', student_id)}' deleted along with {deleted_att.deleted_count} attendance records!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error deleting student: {str(e)}")

        with del_tab2:
            st.markdown("**Select multiple students to delete at once**")

            # Multi-select for students
            selected_students = st.multiselect(
                "Select Students to Delete",
                options=list(student_options.keys()),
                placeholder="Choose students...",
                key="bulk_delete_students"
            )

            if selected_students:
                st.error(f"⚠️ You are about to delete **{len(selected_students)}** students!")

                # Show selected students
                with st.expander("View selected students", expanded=True):
                    for s in selected_students:
                        st.markdown(f"- {s}")

                # Count total attendance records
                total_att = 0
                student_ids_to_delete = [student_options[s] for s in selected_students]
                for sid in student_ids_to_delete:
                    total_att += collections['attendance'].count_documents({"student_id": sid, **user_filter})

                st.info(f"📝 Total **{total_att}** attendance records will also be deleted.")

                # Confirmation
                confirm_bulk = st.checkbox(f"I confirm I want to delete {len(selected_students)} students", key="confirm_bulk_delete")

                if st.button("🗑️ Delete Selected Students", type="primary", disabled=not confirm_bulk, key="btn_bulk_delete"):
                    try:
                        deleted_students = 0
                        deleted_attendance = 0

                        for sid in student_ids_to_delete:
                            # Delete student
                            result = collections['students'].delete_one({"student_id": sid, **user_filter})
                            if result.deleted_count > 0:
                                deleted_students += 1
                            # Delete attendance records
                            att_result = collections['attendance'].delete_many({"student_id": sid, **user_filter})
                            deleted_attendance += att_result.deleted_count

                        st.success(f"✅ Deleted {deleted_students} students and {deleted_attendance} attendance records!")
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ Error deleting students: {str(e)}")

    st.divider()

    # -------------------- System Information Section --------------------
    st.subheader("ℹ️ System Information")
    st.info(f"Database: MongoDB Atlas (Persistent Cluster)")

    user_filter = get_user_filter()
    students_count = collections['students'].count_documents(user_filter)
    attendance_count = collections['attendance'].count_documents(user_filter)

    col1, col2 = st.columns(2)
    with col1:
        st.metric("👨‍🎓 Students", students_count)
    with col2:
        st.metric("📝 Attendance Records", attendance_count)

    # Show teacher count for admin
    if is_admin():
        teachers_count = user_manager.users_col.count_documents({"role": "teacher"})
        st.metric("👨‍🏫 Teachers", teachers_count)
