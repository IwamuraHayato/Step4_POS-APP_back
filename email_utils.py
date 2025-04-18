# email_utils.py
import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import random

def generate_verification_code():
    return str(random.randint(100000, 999999))

def send_verification_email(to_email: str, code: str):
    message = Mail(
        from_email=os.getenv("FROM_EMAIL"),
        to_emails=to_email,
        subject="【ログイン認証コード】Happy Smile パスポート",
        html_content=f"""
        <p>以下の認証コードを入力してください：</p>
        <h2>{code}</h2>
        <p>このコードの有効期限は5分です。</p>
        """
    )

    try:
        sg = SendGridAPIClient(os.getenv("SENDGRID_API_KEY"))
        response = sg.send(message)
        print("✅ メール送信成功:", response.status_code)
    except Exception as e:
        print("❌ メール送信失敗:", e)
        raise
