# Web 文件传输助手

一个基于 Flask 的轻量级文件传输助手，支持跨设备文件传输、消息搜索、文件预览等功能。

## 功能特性

- **用户系统**：注册、登录、记住我功能
- **文件传输**：支持单文件和文件夹上传/下载
- **消息管理**：支持文本消息、文件消息
- **搜索功能**：支持关键字搜索和时间范围筛选
- **批量操作**：支持批量选择、下载、删除
- **文件预览**：支持图片和 PDF 在线预览
- **拖拽上传**：支持拖拽文件到页面直接上传
- **响应式设计**：适配手机、平板、桌面端

## 技术栈

- **后端**：Flask 3.0 + SQLite
- **前端**：纯 HTML + CSS + JavaScript（无框架）
- **样式**：CSS 变量主题系统、响应式布局
- **安全**：bcrypt 密码加密、Session 认证

## 项目结构

```
dataTransmission/
├── app.py                 # Flask 主应用
├── requirements.txt       # Python 依赖
├── database.sqlite        # SQLite 数据库（自动创建）
├── templates/             # HTML 模板
│   ├── login.html         # 登录页面
│   ├── register.html      # 注册页面
│   ├── dashboard.html     # 仪表盘页面
│   └── chat.html          # 主聊天/文件传输页面
├── static/
│   └── css/
│       ├── style.css      # 登录/注册/仪表盘样式
│       └── chat.css       # 聊天页面样式
└── uploads/               # 文件上传目录（自动创建）
```

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/yaohuichong/dataTransmission.git
cd dataTransmission
```

### 2. 创建虚拟环境

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Linux/macOS
python3 -m venv venv
source venv/bin/activate
```

或使用 Conda：

```bash
conda create -n dataTransmission python=3.10
conda activate dataTransmission
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 启动应用

```bash
python app.py
```

### 5. 访问应用

打开浏览器访问：http://127.0.0.1:5000

## 使用说明

### 注册账号

首次使用需要注册账号，点击"注册"按钮填写用户名和密码即可。

### 文件传输

1. 登录后进入主页面
2. 拖拽文件到页面或点击"发送文件"按钮上传
3. 点击文件可预览或下载
4. 支持文件夹整体上传和下载

### 搜索功能

1. 点击搜索按钮打开搜索面板
2. 输入关键字或选择时间范围
3. 支持批量选择和操作

### 批量操作

1. 点击"批量管理"按钮进入批量模式
2. 勾选需要操作的消息
3. 支持批量下载和批量删除

## 配置说明

应用默认配置：

- 监听地址：`0.0.0.0:5000`
- 数据库：SQLite（`database.sqlite`）
- 上传目录：`uploads/`
- 最大文件大小：无限制

如需修改配置，请编辑 `app.py` 文件。

## 注意事项

- 本项目仅供学习和个人使用
- 生产环境请使用专业的 WSGI 服务器（如 Gunicorn）
- 建议配置 HTTPS 以保护数据传输安全

## License

MIT License
