import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings

logger = logging.getLogger(__name__)


def _send(to: str, subject: str, plain: str, html: str) -> None:
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{settings.SMTP_FROM_NAME} <{settings.EMAIL_FROM}>"
    msg["To"] = to
    msg.attach(MIMEText(plain, "plain"))
    msg.attach(MIMEText(html, "html"))

    ctx = ssl.create_default_context()
    with smtplib.SMTP(settings.EMAIL_HOST, settings.EMAIL_PORT) as server:
        server.ehlo()
        server.starttls(context=ctx)
        server.login(settings.EMAIL_USER, settings.EMAIL_PASS)
        server.sendmail(settings.EMAIL_FROM, to, msg.as_string())


def _get_html(email: str, verification_url: str) -> str:
    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0"/>
  <title>Verify your email</title>
</head>
<body style="margin:0;padding:0;background:#f0f4f4;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f0f4f4;padding:48px 0;">
    <tr>
      <td align="center">
        <table width="520" cellpadding="0" cellspacing="0"
               style="background:#ffffff;border-radius:12px;overflow:hidden;
                      box-shadow:0 4px 24px rgba(0,95,90,.10);">
          <tr>
            <td style="background:#005f5a;padding:36px 40px;text-align:center;">
              <span style="color:#ffffff;font-size:18px;font-weight:800;">Agent Forge</span>
              <br/><br/>
              <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;line-height:1.3;">
                Confirm your email address
              </h1>
            </td>
          </tr>
          <tr>
            <td style="background:#004744;height:3px;font-size:0;line-height:0;">&nbsp;</td>
          </tr>
          <tr>
            <td style="padding:40px 40px 32px;">
              <p style="margin:0 0 20px;color:#374151;font-size:15px;line-height:1.7;">
                Thanks for signing up! Click the button below to confirm your email
                address and activate your account.
              </p>
              <table cellpadding="0" cellspacing="0" width="100%" style="margin-bottom:28px;">
                <tr>
                  <td style="background:#f0f9f8;border-left:3px solid #005f5a;
                              border-radius:0 6px 6px 0;padding:12px 16px;">
                    <p style="margin:0;color:#005f5a;font-size:13px;line-height:1.5;">
                      ⏱ This link expires in
                      <strong>{settings.VERIFICATION_TOKEN_TTL_HOURS} hour(s)</strong>.
                    </p>
                  </td>
                </tr>
              </table>
              <table cellpadding="0" cellspacing="0" width="100%">
                <tr>
                  <td align="center">
                    <a href="{verification_url}"
                       style="display:inline-block;background:#005f5a;color:#ffffff;
                              text-decoration:none;padding:15px 40px;border-radius:8px;
                              font-size:15px;font-weight:700;
                              box-shadow:0 4px 12px rgba(0,95,90,0.3);">
                      Verify Email Address →
                    </a>
                  </td>
                </tr>
              </table>
              <p style="margin:28px 0 0;color:#9ca3af;font-size:12px;line-height:1.7;">
                Button not working? Copy and paste this link:<br/>
                <a href="{verification_url}"
                   style="color:#005f5a;word-break:break-all;font-size:11px;">
                  {verification_url}
                </a>
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding:0 40px;">
              <div style="border-top:1px solid #e5e7eb;"></div>
            </td>
          </tr>
          <tr>
            <td style="padding:24px 40px 32px;text-align:center;">
              <p style="margin:0;color:#9ca3af;font-size:12px;line-height:1.7;">
                If you didn't create an account, you can safely ignore this email.<br/>
                This email was sent to <strong style="color:#6b7280;">{email}</strong>
              </p>
            </td>
          </tr>
          <tr>
            <td style="background:#f9fafb;border-top:1px solid #e5e7eb;
                        padding:16px 40px;text-align:center;">
              <p style="margin:0;color:#9ca3af;font-size:11px;letter-spacing:0.3px;">
                © 2025 Agent Forge. All rights reserved.
              </p>
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_verification_email(email: str, token: str) -> None:
    verification_url = (
        f"{settings.FRONTEND_URL.rstrip('/')}/confirm-email?token={token}&email={email}"
    )
    plain = (
        f"Hi,\n\nThanks for signing up! Verify your email by visiting:\n\n"
        f"{verification_url}\n\n"
        f"This link expires in {settings.VERIFICATION_TOKEN_TTL_HOURS} hour(s).\n\n"
        f"— The Agent Forge Team"
    )
    try:
        _send(email, "Verify your email address", plain, _get_html(email, verification_url))
        logger.info("Verification email queued")
    except Exception:
        logger.exception("Failed to send verification email")
        raise


def send_password_reset_email(_to_email: str, _reset_url: str) -> None:
    logger.info("Password reset email queued")
