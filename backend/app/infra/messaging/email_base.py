"""Email service interface and implementations."""
from abc import ABC, abstractmethod
from app.settings import settings
import logging

logger = logging.getLogger(__name__)


class EmailService(ABC):
    """Email service interface."""

    @abstractmethod
    async def send_invite(
        self,
        to_email: str,
        inviter_name: str,
        relationship_type: str,
        token: str,
    ) -> None:
        """Send relationship invitation email."""
        pass


class ConsoleEmailService(EmailService):
    """Console email service (logs to console for MVP)."""

    async def send_invite(
        self,
        to_email: str,
        inviter_name: str,
        relationship_type: str,
        token: str,
    ) -> None:
        """Send invitation email (console stub)."""
        app_url = settings.app_public_url
        invite_url = f"{app_url}/invite?token={token}"
        
        logger.info(
            f"📧 [EMAIL] Sending invite to {to_email}\n"
            f"   From: {inviter_name}\n"
            f"   Relationship: {relationship_type}\n"
            f"   Invite URL: {invite_url}"
        )
        print(f"\n{'='*60}")
        print(f"📧 INVITATION EMAIL (stub)")
        print(f"{'='*60}")
        print(f"To: {to_email}")
        print(f"From: {inviter_name}")
        print(f"Subject: You've been invited to join a {relationship_type} relationship")
        print(f"\n{inviter_name} has invited you to join their {relationship_type} relationship on Project Inside.")
        print(f"\nClick here to accept: {invite_url}")
        print(f"{'='*60}\n")


class SendGridEmailService(EmailService):
    """SendGrid email service for production email sending."""

    def __init__(self, api_key: str, from_email: str, from_name: str):
        """Initialize SendGrid email service."""
        self.api_key = api_key
        self.from_email = from_email
        self.from_name = from_name

    async def send_invite(
        self,
        to_email: str,
        inviter_name: str,
        relationship_type: str,
        token: str,
    ) -> None:
        """Send invitation email via SendGrid."""
        app_url = settings.app_public_url
        invite_url = f"{app_url}/invite?token={token}"
        
        # Print invitation link for debugging
        print(f"\n{'='*80}")
        print(f"🔗 INVITATION LINK")
        print(f"{'='*80}")
        print(f"Invite URL: {invite_url}")
        print(f"To: {to_email}")
        print(f"From: {inviter_name}")
        print(f"Relationship: {relationship_type}")
        print(f"{'='*80}\n")
        logger.info(f"🔗 [INVITE] Invitation link: {invite_url}")
        
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import Mail, Email, To, Content
        except ImportError as import_err:
            error_msg = f"SendGrid package not installed or import failed: {str(import_err)}. Install with: pip install sendgrid==6.11.0"
            logger.error(f"❌ [EMAIL] {error_msg}")
            # Fall back to console email service behavior
            logger.warning("⚠️ [EMAIL] Falling back to console email logging")
            logger.info(
                f"📧 [EMAIL] Would send invite to {to_email}\n"
                f"   From: {inviter_name}\n"
                f"   Relationship: {relationship_type}\n"
                f"   Invite URL: {invite_url}"
            )
            raise ImportError(error_msg) from import_err

        # Create email content
        subject = f"You've been invited to join a {relationship_type} relationship"
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
        </head>
        <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f8f9fa; padding: 30px; border-radius: 8px; text-align: center; margin-bottom: 30px;">
                <h1 style="color: #1e293b; margin: 0;">Project Inside</h1>
            </div>
            
            <div style="background-color: #ffffff; padding: 30px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                <h2 style="color: #1e293b; margin-top: 0;">You've been invited!</h2>
                
                <p style="font-size: 16px; color: #475569;">
                    <strong>{inviter_name}</strong> has invited you to join their <strong>{relationship_type}</strong> relationship on Project Inside.
                </p>
                
                <p style="font-size: 16px; color: #475569;">
                    Project Inside is a relationship coaching platform that helps couples and families improve communication and build stronger connections.
                </p>
                
                <div style="text-align: center; margin: 40px 0;">
                    <a href="{invite_url}" 
                       style="background-color: #1e293b; color: #ffffff; padding: 14px 28px; text-decoration: none; border-radius: 6px; font-weight: 600; display: inline-block; font-size: 16px;">
                        Accept Invitation
                    </a>
                </div>
                
                <p style="font-size: 14px; color: #64748b; margin-top: 30px;">
                    Or copy and paste this link into your browser:<br>
                    <a href="{invite_url}" style="color: #3b82f6; word-break: break-all;">{invite_url}</a>
                </p>
            </div>
            
            <div style="text-align: center; margin-top: 30px; padding-top: 20px; border-top: 1px solid #e2e8f0;">
                <p style="font-size: 12px; color: #94a3b8;">
                    This invitation will expire in 7 days. If you didn't expect this invitation, you can safely ignore this email.
                </p>
            </div>
        </body>
        </html>
        """
        
        text_content = f"""
        You've been invited to join a {relationship_type} relationship on Project Inside.
        
        {inviter_name} has invited you to join their {relationship_type} relationship on Project Inside.
        
        Project Inside is a relationship coaching platform that helps couples and families improve communication and build stronger connections.
        
        Accept your invitation by clicking this link:
        {invite_url}
        
        This invitation will expire in 7 days. If you didn't expect this invitation, you can safely ignore this email.
        """
        
        # Create SendGrid message
        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=To(to_email),
                subject=subject,
                plain_text_content=Content("text/plain", text_content),
                html_content=Content("text/html", html_content)
            )
            
            # Send email
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            if response.status_code in [200, 201, 202]:
                logger.info(f"✅ [EMAIL] Invite email sent successfully to {to_email} (status: {response.status_code})")
                logger.info(f"🔗 [INVITE] Invitation link: {invite_url}")
            else:
                logger.error(f"❌ [EMAIL] Failed to send invite email to {to_email} (status: {response.status_code}, body: {response.body})")
                raise Exception(f"SendGrid API returned status {response.status_code}")
        except Exception as e:
            logger.error(f"❌ [EMAIL] Error sending invite email to {to_email}: {str(e)}")
            raise


def get_email_service() -> EmailService:
    """Get the appropriate email service based on configuration."""
    if settings.sendgrid_api_key:
        # Check if sendgrid package is available
        try:
            import sendgrid
            return SendGridEmailService(
                api_key=settings.sendgrid_api_key,
                from_email=settings.email_from_address,
                from_name=settings.email_from_name
            )
        except ImportError:
            logger.warning("⚠️ [EMAIL] SendGrid API key configured but package not installed. Using console email service.")
            logger.warning("⚠️ [EMAIL] Install SendGrid with: pip install sendgrid==6.11.0")
            return ConsoleEmailService()
    else:
        logger.warning("⚠️ [EMAIL] No SendGrid API key configured. Using console email service (emails will not be sent).")
        return ConsoleEmailService()
