# -*- coding: utf-8 -*-
import uvicorn
from app import create_app, get_config

config = get_config()

app = create_app(config)

if __name__ == '__main__':
    print("=" * 50)
    print("Web 文件传输助手启动成功!")
    print(f"数据库位置: {config.DATABASE}")
    print(f"上传目录: {config.UPLOAD_FOLDER}")
    print("请在浏览器中访问: http://127.0.0.1:5000")
    print("API 文档: http://127.0.0.1:5000/docs")
    print("=" * 50)
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=5000
    )
