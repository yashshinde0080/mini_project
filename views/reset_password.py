"""
Reset Password View
Handles the password reset completion flow - Clean, standard website style
"""

import streamlit as st
import re


def render(user_manager, token):
    """
    Render the Reset Password page - Clean, simple flow
    """

    # Clean styling
    st.markdown("""
        <style>
        .reset-container {
            max-width: 400px;
            margin: 40px auto;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            background: white;
            border: 1px solid #e0e0e0;
        }
        .reset-title {
            text-align: center;
            color: #1a1a1a;
            margin-bottom: 8px;
            font-size: 24px;
            font-weight: 600;
        }
        .reset-subtitle {
            text-align: center;
            color: #666;
            font-size: 14px;
            margin-bottom: 24px;
        }
        .success-icon {
            text-align: center;
            font-size: 48px;
            margin-bottom: 16px;
        }
        .strength-bar {
            height: 4px;
            border-radius: 2px;
            margin-top: 8px;
            transition: all 0.3s;
        }
        </style>
    """, unsafe_allow_html=True)

    # Initialize session state
    if "reset_password_success" not in st.session_state:
        st.session_state.reset_password_success = False

    # Success state
    if st.session_state.reset_password_success:
        st.markdown('<div class="reset-container">', unsafe_allow_html=True)
        st.markdown('<div class="success-icon">✅</div>', unsafe_allow_html=True)
        st.markdown('<h2 class="reset-title">Password reset</h2>', unsafe_allow_html=True)
        st.markdown('<p class="reset-subtitle">Your password has been successfully reset.</p>', unsafe_allow_html=True)

        if st.button("Continue to Login", type="primary"):
            st.session_state.reset_password_success = False
            st.session_state.page = "login"
            st.query_params.clear()
            st.rerun()

        st.markdown('</div>', unsafe_allow_html=True)
        return

    # Validate token
    if not token:
        show_invalid_token_error("No reset token provided")
        return

    token_valid, result = user_manager.validate_reset_token(token)

    if not token_valid:
        show_invalid_token_error(result)
        return

    # Token is valid - show reset form
    user_info = result

    st.markdown('<div class="reset-container">', unsafe_allow_html=True)
    st.markdown('<h2 class="reset-title">Set new password</h2>', unsafe_allow_html=True)
    st.markdown(f'<p class="reset-subtitle">Create a new password for your account</p>', unsafe_allow_html=True)

    # Password reset form
    with st.form("reset_password_form"):
        new_password = st.text_input(
            "New password",
            type="password",
            placeholder="Enter new password"
        )

        confirm_password = st.text_input(
            "Confirm password",
            type="password",
            placeholder="Confirm new password"
        )

        # Password strength indicator (outside form for real-time update)
        if new_password:
            strength = get_password_strength(new_password)
            color = {"weak": "#dc3545", "medium": "#ffc107", "strong": "#28a745"}[strength]
            width = {"weak": "33%", "medium": "66%", "strong": "100%"}[strength]
            st.markdown(f'''
                <div style="margin-bottom: 16px;">
                    <div style="display: flex; justify-content: space-between; font-size: 12px; color: #666;">
                        <span>Password strength</span>
                        <span style="color: {color}; text-transform: capitalize;">{strength}</span>
                    </div>
                    <div style="background: #e9ecef; height: 4px; border-radius: 2px; margin-top: 4px;">
                        <div style="background: {color}; width: {width}; height: 100%; border-radius: 2px;"></div>
                    </div>
                </div>
            ''', unsafe_allow_html=True)

        submit = st.form_submit_button("Reset Password", type="primary")

        if submit:
            if not new_password:
                st.error("Please enter a new password")
            elif not confirm_password:
                st.error("Please confirm your password")
            elif new_password != confirm_password:
                st.error("Passwords do not match")
            elif len(new_password) < 8:
                st.error("Password must be at least 8 characters")
            else:
                with st.spinner("Resetting password..."):
                    success, message = user_manager.reset_password(token, new_password)

                    if success:
                        st.session_state.reset_password_success = True
                        st.rerun()
                    else:
                        st.error(message)

    # Back to login
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("← Back to Login"):
        st.session_state.page = "login"
        st.query_params.clear()
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def show_invalid_token_error(error_message):
    """Display error for invalid or expired token"""
    st.markdown("""
        <style>
        .error-container {
            max-width: 400px;
            margin: 40px auto;
            padding: 40px;
            border-radius: 12px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.08);
            background: white;
            border: 1px solid #e0e0e0;
            text-align: center;
        }
        </style>
    """, unsafe_allow_html=True)

    st.markdown('<div class="error-container">', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 48px; margin-bottom: 16px;">⚠️</div>', unsafe_allow_html=True)
    st.markdown('<h2 style="color: #1a1a1a; margin-bottom: 8px;">Link expired</h2>', unsafe_allow_html=True)
    st.markdown('<p style="color: #666; margin-bottom: 24px;">This password reset link has expired or is invalid.</p>', unsafe_allow_html=True)

    if st.button("Request new link", type="primary"):
        st.session_state.page = "forgot_password"
        st.query_params.clear()
        st.rerun()

    st.markdown("<br>", unsafe_allow_html=True)

    if st.button("← Back to Login"):
        st.session_state.page = "login"
        st.query_params.clear()
        st.rerun()

    st.markdown('</div>', unsafe_allow_html=True)


def get_password_strength(password):
    """Calculate password strength"""
    score = 0
    if len(password) >= 8:
        score += 1
    if re.search(r'[A-Z]', password):
        score += 1
    if re.search(r'[a-z]', password):
        score += 1
    if re.search(r'\d', password):
        score += 1
    if re.search(r'[@$!%*?&#]', password):
        score += 1

    if score <= 2:
        return "weak"
    elif score <= 4:
        return "medium"
    else:
        return "strong"

