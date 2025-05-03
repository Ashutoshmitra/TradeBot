import smtplib
import os
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email.mime.text import MIMEText
from email.utils import formatdate
from email import encoders
from datetime import datetime

def send_email(
    send_from='ashutoshmitra7@gmail.com',
    send_to=['ashutoshmitra7@gmail.com', 'ashmitra0000007@gmail.com'],
    subject='Trade-In/Sell-Off Values Update',
    text='Please find attached the latest trade-in and sell-off values.',
    files=['tradein_values.xlsx'],
    server='smtp.gmail.com',
    port=587,
    username='ashutoshmitra7@gmail.com',
    password=None,
    runtime=None  # New parameter for runtime
):
    # Get password from environment variable
    if password is None:
        password = os.environ.get('EMAIL_PASSWORD')
        if not password:
            raise ValueError("Email password not provided")
    
    # Convert send_to to a list if it's a string
    if isinstance(send_to, str):
        send_to = [send_to]
    
    # Setup email
    msg = MIMEMultipart()
    msg['From'] = send_from
    msg['To'] = ', '.join(send_to)
    msg['Date'] = formatdate(localtime=True)
    msg['Subject'] = subject
    
    # Add email body
    current_date = datetime.now().strftime("%Y-%m-%d")
    runtime_text = f"<p>It took about {runtime} to compile this information.</p>" if runtime else ""
    email_body = f"""
    <html>
    <body>
        <h2>Trade-In / Sell-Off Values Update - {current_date}</h2>
        <p>Hello,</p>
        <p>{text}</p>
        <p>I've attached an Excel file with the latest trade-in values collected from various websites.</p>
        {runtime_text}
        <p>Best regards,<br>Ashutosh</p>
    </body>
    </html>
    """
    msg.attach(MIMEText(email_body, 'html'))
    
    # Attach files
    for file in files:
        if os.path.exists(file):
            part = MIMEBase('application', "octet-stream")
            with open(file, 'rb') as file_obj:
                part.set_payload(file_obj.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition',
                           f'attachment; filename="{os.path.basename(file)}"')
            msg.attach(part)
        else:
            print(f"Warning: File {file} does not exist and will not be attached")
    
    # Send email
    try:
        smtp = smtplib.SMTP(server, port)
        smtp.starttls()
        smtp.login(username, password)
        smtp.sendmail(send_from, send_to, msg.as_string())
        smtp.close()
        print(f"Email successfully sent to {', '.join(send_to)}")
    except Exception as e:
        print(f"Failed to send email: {e}")

if __name__ == "__main__":
    send_email()