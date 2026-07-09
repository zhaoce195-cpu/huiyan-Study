# 慧眼医疗云平台 - 服务器部署脚本
# 使用方式：.\deploy.ps1

$SERVER = "113.219.243.122"
$USER = "root"
$REMOTE_DIR = "/root/huiyan"

Write-Host "========== 慧眼医疗云平台部署 ==========" -ForegroundColor Cyan

# 1. 构建前端
Write-Host "`n[1/5] 构建前端..." -ForegroundColor Yellow
cd frontend
npm run build
if ($LASTEXITCODE -ne 0) {
    Write-Host "前端构建失败" -ForegroundColor Red
    exit 1
}
cd ..

# 2. 打包项目（排除 node_modules / .venv / __pycache__）
Write-Host "`n[2/5] 打包项目..." -ForegroundColor Yellow
tar -czf huiyan-deploy.tar.gz `
    --exclude="frontend/node_modules" `
    --exclude="frontend/.vite" `
    --exclude="backend/__pycache__" `
    --exclude="backend/.venv" `
    --exclude="backend/**/__pycache__" `
    --exclude=".git" `
    backend frontend

Write-Host "打包完成：$(Get-Item huiyan-deploy.tar.gz | Select-Object -ExpandProperty Length) 字节" -ForegroundColor Green

# 3. 上传到服务器
Write-Host "`n[3/5] 上传到服务器..." -ForegroundColor Yellow
scp huiyan-deploy.tar.gz ${USER}@${SERVER}:/root/
if ($LASTEXITCODE -ne 0) {
    Write-Host "上传失败，请检查网络或密码" -ForegroundColor Red
    exit 1
}

# 4. 服务器端解压 + 重启服务
Write-Host "`n[4/5] 服务器端部署..." -ForegroundColor Yellow
ssh ${USER}@${SERVER} @"
cd /root
rm -rf huiyan_old
mv huiyan huiyan_old 2>/dev/null || true
mkdir -p huiyan
tar -xzf huiyan-deploy.tar.gz -C huiyan
cd huiyan/backend

# 激活虚拟环境并安装依赖
source venv/bin/activate 2>/dev/null || python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# 重启后端服务（假设使用 systemd）
sudo systemctl restart huiyan-backend 2>/dev/null || echo '请手动重启后端服务'

# 更新前端静态文件（假设 nginx 指向 /var/www/huiyan）
sudo rm -rf /var/www/huiyan
sudo cp -r /root/huiyan/frontend/dist /var/www/huiyan
sudo chown -R www-data:www-data /var/www/huiyan
sudo systemctl reload nginx

echo '部署完成'
"@

# 5. 清理本地临时文件
Write-Host "`n[5/5] 清理临时文件..." -ForegroundColor Yellow
Remove-Item huiyan-deploy.tar.gz -ErrorAction SilentlyContinue

Write-Host "`n========== 部署完成 ==========" -ForegroundColor Green
Write-Host "前端地址: http://${SERVER}" -ForegroundColor Cyan
Write-Host "后端 API: http://${SERVER}:8000/api" -ForegroundColor Cyan
