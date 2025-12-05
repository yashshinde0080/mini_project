"""
Forgot Password View
Handles the password reset request flow - Standard website style
"""

import streamlit as st
from email_utils import send_password_reset_email, is_email_configured


def render(user_manager):
    """
    Render the Forgot Password page - Clean, simple flow like standard websites
    """

    # Clean centered styling
    st.markdown("""
        <style>
        .forgot-container {
            max-width: 400px;
            margin: 40px auto;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            background: white;
            border: 1px solid #e0e0e0;
        }
        .forgot-title {
            text-align: center;
            color: #1a1a1a;
            margin-bottom: 8px;
            font-size: 24px;
            font-weight: 600;
        }
        .forgot-subtitle {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 30px;
            line-height: 1.5;
        }
        .success-container {
            text-align: center;
            padding: 20px;
        }
        .success-icon {
            font-size: 48px;
            margin-bottom: 16px;
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize session state
    if "forgot_password_sent" not in st.session_state:
        st.session_state.forgot_password_sent = False
    if "forgot_password_email" not in st.session_state:
        st.session_state.forgot_password_email = ""

    # Check email configuration silently
    email_configured, _ = is_email_configured()

    # Success state - Email sent
    if st.session_state.forgot_password_sent:
        st.markdown('<div class="forgot-container">', unsafe_allow_html=True)
        st.markdown('<div class="success-container">', unsafe_allow_html=True)
        st.markdown('<div class="success-icon">✉️</div>', unsafe_allow_html=True)
        st.markdown('<h2 class="forgot-title">Check your email</h2>', unsafe_allow_html=True)
        st.markdown(f'''
            <p class="forgot-subtitle">
                We sent a password reset link to<br>
                <strong>{st.session_state.forgot_password_email}</strong>
            </p>
        ''', unsafe_allow_html=True)
        st.markdown('</div>', unsafe_allow_html=True)

        st.info("💡 Didn't receive the email? Check your spam folder or try again.")

        col1, col2 = st.columns(2)
        with col1:
            if st.button("🔄 Resend Email", type="primary"):
                st.session_state.forgot_password_sent = False
                st.rerun()
        with col2:
            if st.button("← Back to Login"):
                st.session_state.forgot_password_sent = False
                st.session_state.forgot_password_email = ""
                st.session_state.page = "login"
                st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Main form
    st.markdown('<div class="forgot-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="forgot-title">Forgot password?</h2>', unsafe_allow_html=True)
    st.markdown('<p class="forgot-subtitle">No worries, we\'ll send you reset instructions.</p>', unsafe_allow_html=True)

    with st.form("forgot_password_form", clear_on_submit=False):
        email = st.text_input(
            "Email",
            placeholder="Enter your email address",
            label_visibility="collapsed"
        )

        submit = st.form_submit_button("Reset Password", type="primary")

        if submit:
            if not email:
                st.error("Please enter your email address")
            elif not user_manager.validate_email(email):
                st.error("Please enter a valid email address")
            else:
                # Show loading spinner
                with st.spinner("Sending reset link..."):
                    # Generate reset token
                    success, token, result = user_manager.generate_reset_token(email)

                    if success:
                        user_name = result

                        if email_configured:
                            # Send email
                            email_sent, _ = send_password_reset_email(email, token, user_name)

                            if email_sent:
                                st.session_state.forgot_password_sent = True
                                st.session_state.forgot_password_email = email
                                st.rerun()
                            else:
                                # Email failed but don't reveal details - show generic success
                                st.session_state.forgot_password_sent = True
                                st.session_state.forgot_password_email = email
                                st.rerun()
                        else:
                            # Email not configured - still show success (security)
                            st.session_state.forgot_password_sent = True
                            st.session_state.forgot_password_email = email
                            st.rerun()
                    else:
                        # User not found - still show success message (security best practice)
                        # Don't reveal if email exists or not
                        st.session_state.forgot_password_sent = True
                        st.session_state.forgot_password_email = email
                        st.rerun()

    # Back to login link
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Back to Login"):
        st.session_state.page = "login"
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)

