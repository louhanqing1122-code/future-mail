import os
import sys
import smtplib
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

# 强行设置时区为北京时间
os.environ['TZ'] = 'Asia/Shanghai'
try:
    import time
    time.tzset()
except AttributeError:
    pass

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emails.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 邮箱配置
SMTP_SERVER = 'smtp.163.com'
SMTP_PORT = 465
SENDER_EMAIL = os.getenv('MAIL_USERNAME', '')
SENDER_PASSWORD = os.getenv('MAIL_PASSWORD', '')

class EmailTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')

with app.app_context():
    db.create_all()

def send_email_action(to_email, content, subject="来自过去的信"):
    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = Header(subject, 'utf-8')
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        server.quit()
        return True, "发送成功"
    except Exception as e:
        print(f"发送报错: {str(e)}")
        return False, str(e)

def check_for_emails():
    with app.app_context():
        now = datetime.now()
        pending_tasks = EmailTask.query.filter(
            EmailTask.scheduled_time <= now,
            EmailTask.status == 'pending'
        ).all()
        for task in pending_tasks:
            success, _ = send_email_action(task.recipient, task.message)
            if success:
                task.status = 'sent'
                db.session.commit()

scheduler = BackgroundScheduler()
scheduler.add_job(func=check_for_emails, trigger="interval", seconds=60)
scheduler.start()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/schedule', methods=['POST'])
def schedule():
    data = request.json
    email = data.get('email')
    message = data.get('message')
    date_str = data.get('date')

    if not all([email, message, date_str]):
        return jsonify({'success': False, 'message': '请填写所有字段'})

    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.quit()
    except Exception as e:
        return jsonify({'success': False, 'message': f'无法连接邮箱: {str(e)}'})

    scheduled_time = datetime.fromisoformat(date_str)
    new_task = EmailTask(recipient=email, message=message, scheduled_time=scheduled_time)
    db.session.add(new_task)
    db.session.commit()

    send_email_action(email, "【系统通知】你的时间胶囊已成功封存！", subject="时间胶囊确认信")
    return jsonify({'success': True, 'message': '信件已存入！'})

# --- 修改了这里 ---
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
