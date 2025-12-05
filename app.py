import os
from datetime import datetime
from flask import Flask, render_template, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from apscheduler.schedulers.background import BackgroundScheduler
import smtplib
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv

# 1. 加载 .env 文件中的密码
load_dotenv()

app = Flask(__name__)

# 2. 配置数据库 (SQLite)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emails.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# 3. 163 邮箱配置
SMTP_SERVER = 'smtp.163.com'
SMTP_PORT = 465
SENDER_EMAIL = os.getenv('MAIL_USERNAME')
SENDER_PASSWORD = os.getenv('MAIL_PASSWORD')  # 从 .env 读取授权码

# 定义数据库模型
class EmailTask(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    recipient = db.Column(db.String(120), nullable=False)
    message = db.Column(db.Text, nullable=False)
    scheduled_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), default='pending')

# 创建数据库表
with app.app_context():
    db.create_all()

# 发送邮件的函数
def send_email(task):
    try:
        msg = MIMEText(task.message, 'plain', 'utf-8')
        msg['From'] = SENDER_EMAIL
        msg['To'] = task.recipient
        msg['Subject'] = Header('来自过去的信 (Future Mail)', 'utf-8')

        # 连接到网易服务器
        server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        server.login(SENDER_EMAIL, SENDER_PASSWORD)
        server.sendmail(SENDER_EMAIL, [task.recipient], msg.as_string())
        server.quit()
        return True
    except Exception as e:
        print(f"发送失败: {e}")
        return False

# 定时检查任务
def check_for_emails():
    with app.app_context():
        now = datetime.now()
        # 查找所有时间已到且未发送的任务
        pending_tasks = EmailTask.query.filter(
            EmailTask.scheduled_time <= now,
            EmailTask.status == 'pending'
        ).all()

        for task in pending_tasks:
            print(f"正在发送邮件给: {task.recipient}...")
            if send_email(task):
                task.status = 'sent'
                db.session.commit()
                print("发送成功！")

# 启动定时器 (每60秒检查一次)
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

    scheduled_time = datetime.fromisoformat(date_str)
    
    # 简单的验证：必须是未来时间
    if scheduled_time <= datetime.now():
         return jsonify({'success': False, 'message': '时间必须是未来'})

    new_task = EmailTask(recipient=email, message=message, scheduled_time=scheduled_time)
    db.session.add(new_task)
    db.session.commit()

    return jsonify({'success': True, 'message': '信件已存入时间胶囊！'})

if __name__ == '__main__':
    try:
        # 允许外部访问 (host='0.0.0.0')
        app.run(debug=True, host='0.0.0.0', port=5000)
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()