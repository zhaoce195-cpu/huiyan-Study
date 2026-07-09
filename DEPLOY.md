# 慧眼医疗云平台 - 服务器端部署指南

## 一、首次部署（仅第一次需要）

### 1. 安装系统依赖

```bash
# Ubuntu/Debian
sudo apt update
sudo apt install -y python3 python3-pip python3-venv nginx postgresql redis-server

# CentOS/RHEL
sudo yum install -y python3 python3-pip nginx postgresql-server redis
```

### 2. 创建数据库

```bash
sudo -u postgres psql
CREATE DATABASE huiyan_db;
CREATE USER huiyan_user WITH PASSWORD 'your_secure_password';
GRANT ALL PRIVILEGES ON DATABASE huiyan_db TO huiyan_user;
\q
```

### 3. 创建 systemd 服务文件

```bash
sudo nano /etc/systemd/system/huiyan-backend.service
```

粘贴以下内容：

```ini
[Unit]
Description=Huiyan Medical Cloud Backend
After=network.target postgresql.service redis.service

[Service]
Type=simple
User=root
WorkingDirectory=/root/huiyan/backend
Environment="PATH=/root/huiyan/backend/venv/bin"
ExecStart=/root/huiyan/backend/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable huiyan-backend
sudo systemctl start huiyan-backend
```

### 4. 配置 Nginx

```bash
sudo nano /etc/nginx/sites-available/huiyan
```

粘贴以下内容：

```nginx
server {
    listen 80;
    server_name 113.219.243.122;

    # 前端静态文件
    location / {
        root /var/www/huiyan;
        try_files $uri $uri/ /index.html;
    }

    # 后端 API 代理
    location /api/ {
        proxy_pass http://127.0.0.1:8000/api/;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_cache_bypass $http_upgrade;
        client_max_body_size 100M;
    }
}
```

启用站点：

```bash
sudo ln -s /etc/nginx/sites-available/huiyan /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### 5. 配置后端环境变量

```bash
cd /root/huiyan/backend
nano .env
```

粘贴：

```ini
# 数据库
DATABASE_URL=postgresql://huiyan_user:your_secure_password@localhost/huiyan_db

# JWT 密钥（生成随机字符串）
SECRET_KEY=your_random_secret_key_here

# Redis
REDIS_URL=redis://localhost:6379/0

# 上传目录
UPLOAD_DIR=/root/huiyan/backend/uploads

# 允许的跨域
CORS_ORIGINS=http://113.219.243.122,https://113.219.243.122
```

### 6. 初始化数据库

```bash
cd /root/huiyan/backend
source venv/bin/activate
alembic upgrade head
python -m app.scripts.init_db  # 如果有初始化脚本
```

---

## 二、日常更新部署（已完成首次部署后）

在本地 Windows 执行：

```powershell
cd "d:/huiyan cloude"
.\deploy.ps1
```

输入密码：`Boxiang2023!`

---

## 三、常用运维命令

### 查看后端日志
```bash
sudo journalctl -u huiyan-backend -f
```

### 查看后端状态
```bash
sudo systemctl status huiyan-backend
```

### 重启服务
```bash
sudo systemctl restart huiyan-backend
sudo systemctl reload nginx
```

### 查看 Nginx 错误日志
```bash
sudo tail -f /var/log/nginx/error.log
```

---

## 四、防火墙设置

```bash
# UFW (Ubuntu)
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw allow 22/tcp
sudo ufw enable

# Firewalld (CentOS)
sudo firewall-cmd --permanent --add-service=http
sudo firewall-cmd --permanent --add-service=https
sudo firewall-cmd --reload
```

---

## 五、故障排查

1. **前端无法访问**
   - 检查 Nginx: `sudo nginx -t && sudo systemctl status nginx`
   - 检查文件权限: `ls -la /var/www/huiyan`

2. **后端 API 报错**
   - 查看日志: `sudo journalctl -u huiyan-backend -n 50`
   - 检查数据库连接: `psql -U huiyan_user -d huiyan_db -h localhost`
   - 检查 Redis: `redis-cli ping`

3. **上传文件失败**
   - 检查目录权限: `ls -la /root/huiyan/backend/uploads`
   - 检查 Nginx 大小限制: `client_max_body_size`

---

## 六、备份策略

```bash
# 每日备份脚本
sudo nano /root/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/root/backups"
DATE=$(date +%Y%m%d_%H%M%S)

# 备份数据库
pg_dump -U huiyan_user huiyan_db > $BACKUP_DIR/db_$DATE.sql

# 备份上传文件
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /root/huiyan/backend/uploads

# 删除 7 天前的备份
find $BACKUP_DIR -name "*.sql" -mtime +7 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +7 -delete
```

添加到 crontab：
```bash
sudo crontab -e
0 2 * * * /root/backup.sh
```
