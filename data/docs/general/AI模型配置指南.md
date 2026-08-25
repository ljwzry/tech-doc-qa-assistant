# AI模型配置指南

## 概述
本指南介绍如何为 TechDoc QA Assistant 项目配置 AI 大模型服务。

## 支持的模型提供商
- SiliconFlow（推荐，国内可访问）
- DeepSeek 官方 API
- Ollama 本地模型

## 配置步骤
1. 复制 `.env.example` 为 `.env`
2. 设置 `LLM_PROVIDER`、`LLM_MODEL`、`LLM_API_KEY`
3. 重启后端服务

## 常见问题
- API 超时：检查网络连接
- 429 限流：降低请求频率或升级套餐
- 503 错误：服务暂时不可用，稍后重试
