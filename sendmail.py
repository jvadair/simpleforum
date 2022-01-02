import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


SMTP_URL = "example.com"


def send_verification_code(recipient, recipient_name, verification_code):
    sender_email = "simpleforum@jvadair.com"
    with open('.smtp_passwd') as password_file:
        password = password_file.read()

    message = MIMEMultipart("alternative")
    message["Subject"] = "Email Verification"
    message["From"] = sender_email
    message["To"] = recipient

    # Create the plain-text and HTML version of your message
    with open('verification_template.html', 'r') as templateobj:
        html = templateobj.read()
        html = html.replace('$$name', recipient_name)
        html = html.replace('$$verification_code', verification_code)

    # Turn these into plain/html MIMEText objects
    # part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    # Add HTML/plain-text parts to MIMEMultipart message
    # The email client will try to render the last part first
    # message.attach(part1)
    message.attach(part2)

    # Create secure connection with server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_URL, 465, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(
            sender_email, recipient, message.as_string()
        )

def send_thread_notif(recipient, recipient_name, forum, author, content):
    sender_email = "simpleforum@jvadair.com"
    with open('.smtp_passwd') as password_file:
        password = password_file.read()

    message = MIMEMultipart("alternative")
    message["Subject"] = f"New message on {forum}"
    message["From"] = sender_email
    message["To"] = recipient

    # Create the plain-text and HTML version of your message
    with open('forum_notif_template.html', 'r') as templateobj:
        html = templateobj.read()
        html = html.replace('$$name', recipient_name)
        html = html.replace('$$forum', forum)
        html = html.replace('$$author', author)
        html = html.replace('$$content', content)

    # Turn these into plain/html MIMEText objects
    # part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")

    # Add HTML/plain-text parts to MIMEMultipart message
    # The email client will try to render the last part first
    # message.attach(part1)
    message.attach(part2)

    # Create secure connection with server and send email
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(SMTP_URL, 465, context=context) as server:
        server.login(sender_email, password)
        server.sendmail(
            sender_email, recipient, message.as_string()
        )
