"""
Email Utilities for Password Reset
Supports both SMTP (development) and SendGrid (production)
"""

import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Tuple
import streamlit as st
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# -------------------- Configuration --------------------
# SMTP Configuration (Development)
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USERNAME = os.getenv("SMTP_USERNAME", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")  # For Gmail, use App Password
SMTP_FROM_EMAIL = os.getenv("SMTP_FROM_EMAIL", "")
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Smart Attendance System")

# SendGrid Configuration (Production)
SENDGRID_API_KEY = os.getenv("SENDGRID_API_KEY", "")
SENDGRID_FROM_EMAIL = os.getenv("SENDGRID_FROM_EMAIL", "")
SENDGRID_FROM_NAME = os.getenv("SENDGRID_FROM_NAME", "Smart Attendance System")

# Application URL for reset links
APP_URL = os.getenv("APP_URL")

# Email Provider Selection
EMAIL_PROVIDER = os.getenv("EMAIL_PROVIDER", "smtp")  # "smtp" or "sendgrid"


def get_reset_link(token: str) -> str:
    """Generate the password reset link with token"""
    return f"{APP_URL}?reset_token={token}"


def get_email_template(reset_link: str, user_name: str = "User") -> Tuple[str, str]:
    """
    Generate HTML and plain text email templates
    Returns: (html_content, plain_text_content)
    """
    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 30px; text-align: center; border-radius: 10px 10px 0 0;">
            <h1 style="color: white; margin: 0; font-size: 28px;">🔐 Password Reset Request</h1>
        </div>
        
        <div style="background-color: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; border: 1px solid #ddd; border-top: none;">
            <p style="font-size: 16px;">Hello <strong>{user_name}</strong>,</p>
            
            <p style="font-size: 16px;">We received a request to reset your password for your Smart Attendance System account.</p>
            
            <div style="text-align: center; margin: 30px 0;">
                <a href="{reset_link}" 
                   style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                          color: white; 
                          padding: 15px 40px; 
                          text-decoration: none; 
                          border-radius: 25px; 
                          font-size: 16px; 
                          font-weight: bold;
                          display: inline-block;
                          box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);">
                    Reset My Password
                </a>
            </div>
            
            <p style="font-size: 14px; color: #666;">Or copy and paste this link into your browser:</p>
            <p style="font-size: 12px; background-color: #eee; padding: 10px; border-radius: 5px; word-break: break-all;">
                {reset_link}
            </p>
            
            <div style="background-color: #fff3cd; border: 1px solid #ffc107; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p style="margin: 0; font-size: 14px; color: #856404;">
                    ⚠️ <strong>Important:</strong> This link will expire in <strong>30 minutes</strong> for security reasons.
                </p>
            </div>
            
            <p style="font-size: 14px; color: #666;">If you didn't request this password reset, please ignore this email. Your password will remain unchanged.</p>
            
            <hr style="border: none; border-top: 1px solid #ddd; margin: 30px 0;">
            
            <p style="font-size: 12px; color: #999; text-align: center;">
                This is an automated message from Smart Attendance System.<br>
                Please do not reply to this email.
            </p>
        </div>
    </body>
    </html>
    """
    
    plain_text = f"""
Password Reset Request

Hello {user_name},

We received a request to reset your password for your Smart Attendance System account.

Click the link below to reset your password:
{reset_link}

IMPORTANT: This link will expire in 30 minutes for security reasons.

If you didn't request this password reset, please ignore this email. Your password will remain unchanged.

---
This is an automated message from Smart Attendance System.
Please do not reply to this email.
    """
    
    return html_content, plain_text


def send_email_smtp(to_email: str, subject: str, html_content: str, plain_text: str) -> Tuple[bool, str]:
    """
    Send email using SMTP (Development/Gmail)
    
    For Gmail:
    1. Enable 2-Factor Authentication
    2. Generate App Password: https://myaccount.google.com/apppasswords
    3. Use App Password as SMTP_PASSWORD
    """
    if not SMTP_USERNAME or not SMTP_PASSWORD:
        return False, "SMTP credentials not configured. Set SMTP_USERNAME and SMTP_PASSWORD environment variables."
    
    try:
        # Create message
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_FROM_EMAIL or SMTP_USERNAME}>"
        msg["To"] = to_email
        
        # Attach plain text and HTML versions
        part1 = MIMEText(plain_text, "plain")
        part2 = MIMEText(html_content, "html")
        msg.attach(part1)
        msg.attach(part2)
        
        # Connect and send
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USERNAME, SMTP_PASSWORD)
            server.sendmail(SMTP_USERNAME, to_email, msg.as_string())
        
        return True, "Email sent successfully"
    
    except smtplib.SMTPAuthenticationError:
        return False, "SMTP authentication failed. Check your credentials."
    except smtplib.SMTPRecipientsRefused:
        return False, "Invalid recipient email address."
    except smtplib.SMTPException as e:
        return False, f"SMTP error: {str(e)}"
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"


def send_email_sendgrid(to_email: str, subject: str, html_content: str, plain_text: str) -> Tuple[bool, str]:
    """
    Send email using SendGrid (Production)
    
    Setup:
    1. Create SendGrid account: https://sendgrid.com
    2. Create API Key with Mail Send permission
    3. Set SENDGRID_API_KEY environment variable
    4. Verify sender email in SendGrid
    """
    if not SENDGRID_API_KEY:
        return False, "SendGrid API key not configured. Set SENDGRID_API_KEY environment variable."
    
    try:
        # Import SendGrid library
        from sendgrid import SendGridAPIClient
        from sendgrid.helpers.mail import Mail, Email, To, Content
        
        message = Mail(
            from_email=Email(SENDGRID_FROM_EMAIL, SENDGRID_FROM_NAME),
            to_emails=To(to_email),
            subject=subject,
            plain_text_content=Content("text/plain", plain_text),
            html_content=Content("text/html", html_content)
        )
        
        sg = SendGridAPIClient(SENDGRID_API_KEY)
        response = sg.send(message)
        
        if response.status_code in [200, 201, 202]:
            return True, "Email sent successfully"
        else:
            return False, f"SendGrid returned status code: {response.status_code}"
    
    except ImportError:
        return False, "SendGrid library not installed. Run: pip install sendgrid"
    except Exception as e:
        return False, f"Failed to send email via SendGrid: {str(e)}"


def send_password_reset_email(to_email: str, token: str, user_name: str = "User") -> Tuple[bool, str]:
    """
    Send password reset email using configured provider
    
    Args:
        to_email: Recipient email address
        token: Password reset token
        user_name: User's display name
    
    Returns:
        Tuple of (success: bool, message: str)
    """
    reset_link = get_reset_link(token)
    subject = "🔐 Password Reset Request - Smart Attendance System"
    html_content, plain_text = get_email_template(reset_link, user_name)
    
    if EMAIL_PROVIDER.lower() == "sendgrid":
        return send_email_sendgrid(to_email, subject, html_content, plain_text)
    else:
        return send_email_smtp(to_email, subject, html_content, plain_text)


def is_email_configured() -> Tuple[bool, str]:
    """
    Check if email sending is properly configured
    
    Returns:
        Tuple of (is_configured: bool, provider_info: str)
    """
    if EMAIL_PROVIDER.lower() == "sendgrid":
        if SENDGRID_API_KEY:
            return True, "SendGrid (Production)"
        return False, "SendGrid API key not configured"
    else:
        if SMTP_USERNAME and SMTP_PASSWORD:
            return True, f"SMTP ({SMTP_HOST})"
        return False, "SMTP credentials not configured"


# -------------------- Development/Testing Helper --------------------
def send_test_email(to_email: str) -> Tuple[bool, str]:
    """Send a test email to verify configuration"""
    return send_password_reset_email(to_email, "TEST_TOKEN_12345", "Test User")

