# 📚 在线教育平台 | Project A

> 基于 Spring Boot + Vue3 + FFmpeg + Redis 的在线课程管理与学习系统

[![License](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)
[![Java](https://img.shields.io/badge/Java-17-orange.svg)](https://openjdk.java.net/)
[![Spring Boot](https://img.shields.io/badge/Spring%20Boot-3.2.0-green.svg)](https://spring.io/projects/spring-boot)
[![Vue](https://img.shields.io/badge/Vue-3.3-42b883.svg)](https://vuejs.org/)
[![FFmpeg](https://img.shields.io/badge/FFmpeg-6.0-red.svg)](https://ffmpeg.org/)
[![Version](https://img.shields.io/badge/version-v1.0.0-brightgreen.svg)](CHANGELOG.md)

---

## 项目简介

在线教育平台是一个面向 C 端学员和 B 端机构的全栈 SaaS 系统，支持课程管理、视频上传转码、在线学习、作业提交、考试评分、社区讨论等完整教育业务流程。后端采用 Spring Boot 3.x + MyBatis-Plus + Redis + RocketMQ，前端使用 Vue3 + Element Plus + Vite，视频处理使用 FFmpeg，文件存储采用阿里云 OSS。

---

## 核心功能

### 📚 课程管理
- 课程创建/编辑/下架
- 课程分类与标签管理
- 课程封面与视频上传
- 课程章节与课时管理
- 课程发布审核流程

### 🎥 视频处理
- 支持 MP4/AVI/MOV 等格式上传
- 自动转码为 MP4 (H.264/AAC)
- 视频封面自动截取
- 视频分片上传与断点续传
- 视频加密防盗链

### 👥 用户管理
- 学员注册/登录/实名认证
- 角色权限：超级管理员/机构管理员/教师/学员
- 用户数据统计（学习时长/完成课程数）
- 用户行为轨迹记录

### 📝 学习追踪
- 学习进度自动记录
- 课后作业在线提交
- 在线考试与自动阅卷
- 学习证书自动生成
- 学习数据分析报表

### 💬 社区互动
- 课程评论与回复
- 问答区@功能
- 点赞与收藏
- 私信系统

### 💰 订单与支付
- 课程购买订单
- 优惠券系统
- 微信/支付宝支付
- 订单退款流程

---

## 技术栈

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| 后端框架 | Spring Boot | 3.2.0 | Java 17 |
| ORM | MyBatis-Plus | 3.5.5 | 持久层 |
| 数据库 | MySQL | 8.0 | 业务数据 |
| 缓存 | Redis | 7.2 | 会话/热点数据 |
| 消息队列 | RocketMQ | 5.0 | 异步处理 |
| 存储服务 | 阿里云 OSS | - | 视频/文件 |
| 视频处理 | FFmpeg | 6.0 | 转码/截封面 |
| 前端框架 | Vue | 3.3 | TypeScript |
| UI 组件 | Element Plus | 2.4 | 管理后台 |
| 移动端 | uni-app | 3.8 | 跨平台 |
| 构建工具 | Vite | 5.0 | 前端构建 |
| 容器化 | Docker | 24.0 | 环境隔离 |

---

## 快速开始

### 环境要求

- JDK 17+
- Maven 3.9+
- Node.js 18+
- MySQL 8.0
- Redis 7.2
- RocketMQ 5.0
- FFmpeg 6.0

### 1. 克隆仓库

```bash
git clone https://github.com/your-org/online-edu.git
cd online-edu
```

### 2. 初始化数据库

```bash
mysql -h127.0.0.1 -P3306 -uroot -proot < scripts/init_schema.sql
mysql -h127.0.0.1 -P3306 -uroot -proot < scripts/insert_test_data.sql
```

### 3. 启动中间件

```bash
docker-compose up -d
```

### 4. 配置环境变量

复制 `application-dev.yml.example` 为 `application-dev.yml`，修改数据库连接、OSS 密钥等配置。

### 5. 启动后端

```bash
mvn clean install -DskipTests
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```

### 6. 启动前端

```bash
cd admin-frontend
npm install
npm run dev
```

访问 http://localhost:5173 进入管理后台（默认账号：admin/admin123）。

---

## 项目结构

```
online-edu/
├── src/main/java/com/onlineedu/
│   ├── OnlineEduApplication.java
│   ├── config/                   # 配置类
│   │   ├── RedisConfig.java
│   │   ├── RocketMQConfig.java
│   │   ├── OSSConfig.java
│   │   └── FFmpegConfig.java
│   ├── controller/               # 控制器
│   │   ├── CourseController.java
│   │   ├── VideoController.java
│   │   ├── OrderController.java
│   │   └── UserController.java
│   ├── service/                  # 业务逻辑
│   │   ├── CourseService.java
│   │   ├── VideoTranscodeService.java
│   │   ├── PaymentService.java
│   │   └── LearningProgressService.java
│   ├── mapper/                   # MyBatis Mapper
│   │   ├── CourseMapper.java
│   │   ├── UserMapper.java
│   │   └── OrderMapper.java
│   ├── mq/                       # RocketMQ 消息处理器
│   │   ├── VideoTranscodeConsumer.java
│   │   └── OrderPaidConsumer.java
│   ├── utils/                    # 工具类
│   │   ├── FFmpegUtil.java
│   │   ├── OSSUtil.java
│   │   └── JwtUtil.java
│   └── enums/                    # 枚举类
├── src/main/resources/
│   ├── application.yml
│   ├── application-dev.yml
│   ├── application-prod.yml
│   ├── mapper/                   # MyBatis XML
│   └── static/                    # 静态资源
├── admin-frontend/               # 管理后台 Vue3
├── student-frontend/             # 学员端 uni-app
├── scripts/
│   ├── init_schema.sql
│   └── insert_test_data.sql
├── docs/
│   ├── architecture.md
│   ├── api-design.md
│   └── deploy-guide.md
└── docker-compose.yml
```

---

## 配置说明

```yaml
# application-dev.yml 核心配置
spring:
  datasource:
    url: jdbc:mysql://localhost:3306/online_edu?useSSL=false&characterEncoding=utf8
    username: root
    password: root
    driver-class-name: com.mysql.cj.jdbc.Driver
    hikari:
      maximum-pool-size: 20
      minimum-idle: 5

  data:
    redis:
      host: localhost
      port: 6379
      timeout: 5000ms
      lettuce:
        pool:
          max-active: 16

  cloud:
    alicloud:
      oss:
        endpoint: https://oss-cn-hangzhou.aliyuncs.com
        bucket-name: online-edu-videos
        access-key-id: YOUR_ACCESS_KEY
        access-key-secret: YOUR_SECRET_KEY

rocketmq:
  name-server: localhost:9876
  producer-group: video-transcode-producer
  consumer-group: video-transcode-consumer

ffmpeg:
  path: /usr/local/bin/ffmpeg
  output-dir: /data/ffmpeg-output
  threads: 4

# JWT 配置
jwt:
  secret: your-secret-key-at-least-256-bits
  expiration: 7200  # 2小时
```

---

## API 文档

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/api/v1/courses` | 创建课程 |
| GET | `/api/v1/courses/{id}` | 获取课程详情 |
| PUT | `/api/v1/courses/{id}` | 更新课程 |
| DELETE | `/api/v1/courses/{id}` | 删除课程 |
| POST | `/api/v1/videos/upload` | 上传视频 |
| GET | `/api/v1/videos/{id}/progress` | 查询转码进度 |
| POST | `/api/v1/orders` | 创建订单 |
| POST | `/api/v1/payments/{id}/pay` | 支付订单 |
| GET | `/api/v1/users/{id}/learning-records` | 学习记录 |
| GET | `/actuator/health` | 健康检查 |

---

## 部署指南

### 开发环境

```bash
docker-compose up -d
mvn spring-boot:run -Dspring-boot.run.profiles=dev
```

### 生产环境

```bash
# 1. 打包
mvn clean package -DskipTests

# 2. 构建镜像
docker build -t online-edu:1.0.0 .

# 3. 启动
docker run -d --name online-edu \
  -p 8080:8080 \
  -e SPRING_PROFILES_ACTIVE=prod \
  -v /data/online-edu/logs:/app/logs \
  online-edu:1.0.0
```

JVM 参数：

```bash
java -Xms512m -Xmx2048m -XX:+UseG1GC -XX:MaxGCPauseMillis=200 \
     -jar online-edu-1.0.0.jar --spring.profiles.active=prod
```

---

## 性能指标

| 指标 | 目标 |
|------|------|
| 并发用户数 | 10,000 |
| 视频转码吞吐 | 100 个/小时 |
| 查询 P95 延迟 | < 150ms |
| 转码端到端延迟 | < 5 分钟/小时长视频 |
| 课程搜索 P95 | < 300ms |

---

## 路线图

- [x] v1.0 基础课程管理 + 视频上传
- [x] v1.5 支付系统 + 订单管理
- [ ] v1.8 学习进度追踪 + 数据分析
- [ ] v2.0 直播课堂 + 互动功能
- [ ] v2.5 AI 智能推荐

---

## 许可证

Apache License 2.0

---

## 联系方式

- **技术支持**：tech@online-edu.com
- **问题反馈**：[GitHub Issues](https://github.com/your-org/online-edu/issues)