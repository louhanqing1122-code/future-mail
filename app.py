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

# 强行设置时区为北京时间，防止 Render 时差问题
os.environ['TZ'] = 'Asia/Shanghai'
try:
    import time
    time.tzset()
except AttributeError:
    pass # Windows系统跳过

load_dotenv()

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emails.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 163 邮箱配置
SMTP_SERVER = 'smtp.163.com'
SMTP_PORT = 465
# 优先从环境变量读，读不到就用空字符串，防止报错
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

# --- 核心发信函数 ---
def send_email_action(to_email, content, subject="来自过去的信"):
    try:
        msg = MIMEText(content, 'plain', 'utf-8')
        msg['From'] = SENDER_EMAIL
        msg['To'] = to_email
        msg['Subject'] = Header(subject, 'utf-8')

        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        # 这里会测试登录，如果密码错，会直接抛出异常
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [to_email], msg.as_string())
        server.quit()
        return True, "发送成功"
    except Exception as e:
        error_msg = str(e)
        print(f"发送报错: {error_msg}") # 打印到后台以防万一
        return False, error_msg

# --- 定时任务 ---
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

# --- 路由 ---
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

    # --- 关键修改：立即进行一次“自我诊断” ---
    # 在用户保存信件前，我们先尝试连接一下 163 邮箱
    # 如果连接失败，直接把错误弹窗告诉用户！
    try:
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.quit()
    except Exception as e:
        # 如果这里报错，说明授权码填错了，或者IP被封了
        return jsonify({'success': False, 'message': f'【严重错误】无法连接邮箱服务器！请检查授权码。详细报错: {str(e)}'})

    # 如果连接成功，再保存任务
    scheduled_time = datetime.fromisoformat(date_str)
    new_task = EmailTask(recipient=email, message=message, scheduled_time=scheduled_time)
    db.session.add(new_task)
    db.session.commit()

    # 为了让你放心，保存成功后，顺便发一封“确认信”给用户
    # 这样你就立刻知道能不能收到了
    send_email_action(email, "【系统通知】你的时间胶囊已成功封存！这封信证明系统是好用的。", subject="时间胶囊确认信")

    return jsonify({'success': True, 'message': '信件已存入！且已发送一封确认邮件到你邮箱，请查收！'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
