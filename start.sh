#!/bin/bash

# 智能教材语料生成平台 - 快速启动脚本

echo "======================================================"
echo "智能教材语料生成与校验平台"
echo "Intelligent Textbook Corpus Generation Platform"
echo "======================================================"
echo ""

# 检查Python版本
echo "检查Python环境..."
python --version
if [ $? -ne 0 ]; then
    echo "错误: 未找到Python,请先安装Python 3.7+"
    exit 1
fi
echo ""

# 检查.env文件
if [ ! -f .env ]; then
    echo "⚠️  未找到.env文件"
    echo "正在创建.env文件..."
    cp .env.example .env
    echo "✓ 已创建.env文件"
    echo ""
    echo "请编辑.env文件并添加您的API密钥:"
    echo "  - MINERU_API_KEY (必需)"
    echo "  - 至少一个LLM API密钥 (OPENAI_API_KEY/GEMINI_API_KEY/DEEPSEEK_API_KEY/KIMI_API_KEY)"
    echo ""
    read -p "是否现在编辑.env文件? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        ${EDITOR:-nano} .env
    else
        echo "请稍后手动编辑.env文件"
        exit 0
    fi
fi

# 检查是否已安装依赖
echo "检查依赖..."
if ! python -c "import flask" 2>/dev/null; then
    echo "需要安装依赖包..."
    read -p "是否现在安装? (y/n) " -n 1 -r
    echo ""
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        pip install -r requirements.txt
    else
        echo "请运行: pip install -r requirements.txt"
        exit 0
    fi
fi
echo "✓ 依赖已安装"
echo ""

# 运行测试
echo "运行基础测试..."
python test_setup.py
if [ $? -ne 0 ]; then
    echo "测试失败,请检查配置"
    exit 1
fi
echo ""

# 启动应用
echo "======================================================"
echo "启动Flask应用..."
echo "======================================================"
echo ""
echo "应用将在以下地址运行:"
echo "  👉 http://localhost:5000"
echo ""
echo "按 Ctrl+C 停止应用"
echo ""

python app.py
