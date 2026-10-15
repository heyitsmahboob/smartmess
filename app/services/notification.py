from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
import logging
from datetime import datetime
from app.database import db_session

logger = logging.getLogger("smartmess.notifications")

class BaseNotificationProvider(ABC):
    """Abstract notification provider for extensible multi-channel notifications."""
    
    @property
    @abstractmethod
    def channel_name(self) -> str:
        pass

    @abstractmethod
    def send(self, recipient: Dict[str, Any], title: str, message: str, action_url: Optional[str] = None) -> bool:
        pass

class InAppNotificationProvider(BaseNotificationProvider):
    @property
    def channel_name(self) -> str:
        return "in_app"

    def send(self, recipient: Dict[str, Any], title: str, message: str, action_url: Optional[str] = None) -> bool:
        user_id = recipient.get("id")
        if not user_id:
            return False
        try:
            with db_session() as conn:
                conn.execute("""
                    INSERT INTO notifications (user_id, title, message, type, action_url)
                    VALUES (?, ?, ?, 'system', ?)
                """, (user_id, title, message, action_url))
            return True
        except Exception as e:
            logger.error(f"InApp notification error: {e}")
            return False

class EmailNotificationProvider(BaseNotificationProvider):
    @property
    def channel_name(self) -> str:
        return "email"

    def send(self, recipient: Dict[str, Any], title: str, message: str, action_url: Optional[str] = None) -> bool:
        email = recipient.get("email")
        if not email:
            return False
        # External provider simulation / hook (e.g. SendGrid / AWS SES / SMTP)
        logger.info(f"[EMAIL DISPATCH] To: {email} | Subject: {title} | Body: {message}")
        return True

class SmsNotificationProvider(BaseNotificationProvider):
    @property
    def channel_name(self) -> str:
        return "sms"

    def send(self, recipient: Dict[str, Any], title: str, message: str, action_url: Optional[str] = None) -> bool:
        phone = recipient.get("phone")
        if not phone:
            return False
        # External provider simulation / hook (e.g. Twilio / Gupshup / MSG91)
        logger.info(f"[SMS DISPATCH] To: {phone} | SMS: {title}: {message}")
        return True

class WhatsAppNotificationProvider(BaseNotificationProvider):
    @property
    def channel_name(self) -> str:
        return "whatsapp"

    def send(self, recipient: Dict[str, Any], title: str, message: str, action_url: Optional[str] = None) -> bool:
        phone = recipient.get("phone")
        if not phone:
            return False
        # External provider simulation / hook (e.g. WhatsApp Business Cloud API)
        logger.info(f"[WHATSAPP DISPATCH] To: {phone} | Message: *{title}*\n{message}\nQuick Link: {action_url or ''}")
        return True

class WebPushNotificationProvider(BaseNotificationProvider):
    @property
    def channel_name(self) -> str:
        return "web_push"

    def send(self, recipient: Dict[str, Any], title: str, message: str, action_url: Optional[str] = None) -> bool:
        logger.info(f"[PUSH DISPATCH] User {recipient.get('id')} | {title}: {message}")
        return True

class NotificationService:
    def __init__(self):
        self.providers: Dict[str, BaseNotificationProvider] = {
            "in_app": InAppNotificationProvider(),
            "email": EmailNotificationProvider(),
            "sms": SmsNotificationProvider(),
            "whatsapp": WhatsAppNotificationProvider(),
            "web_push": WebPushNotificationProvider()
        }

    def register_provider(self, provider: BaseNotificationProvider):
        self.providers[provider.channel_name] = provider

    def notify_user(
        self,
        user: Dict[str, Any],
        title: str,
        message: str,
        action_url: Optional[str] = None,
        channels: Optional[List[str]] = None
    ) -> Dict[str, bool]:
        if channels is None:
            channels = ["in_app", "whatsapp"]  # Default channels for hostels
        
        results = {}
        for ch in channels:
            provider = self.providers.get(ch)
            if provider:
                results[ch] = provider.send(user, title, message, action_url)
        return results

    def broadcast_meal_reminder(self, meal_id: int, reminder_type: str = "open") -> int:
        """Broadcast reminder to all active residents who have not yet responded."""
        with db_session() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, meal_type, meal_date, meal_time, response_deadline FROM meals WHERE id = ?", (meal_id,))
            meal = cursor.fetchone()
            if not meal:
                return 0

            # Find residents who haven't responded yet
            cursor.execute("""
                SELECT u.id, u.full_name, u.email, u.phone
                FROM users u
                WHERE u.status = 'active'
                  AND u.id NOT IN (SELECT user_id FROM meal_responses WHERE meal_id = ?)
            """, (meal_id,))
            unresponded_users = cursor.fetchall()

            meal_title = meal["meal_type"].capitalize()
            deadline_str = meal["response_deadline"]

            if reminder_type == "deadline_approaching":
                title = f"⏰ 1 Hour Left: Respond for {meal_title}!"
                msg = f"Response deadline for today's {meal_title} is approaching ({deadline_str}). Please confirm if you will eat."
            else:
                title = f"🍽️ {meal_title} Response is Open"
                msg = f"Will you eat {meal_title} today? Response closes at {deadline_str}. Tap to confirm in 2 seconds."

            count = 0
            for u in unresponded_users:
                user_dict = dict(u)
                self.notify_user(user_dict, title, msg, action_url=f"/dashboard")
                count += 1

            return count

notification_service = NotificationService()
