# Project A — 在线教育平台系统架构设计文档

> 版本：v1.0.0 | 更新日期：2026-07-28 | 作者：架构组

## 1. 系统概述

本系统是一个面向学员和教育机构的 **B2C 在线教育 SaaS 平台**，提供课程发布、视频点播、在线学习、订单支付、学习追踪、社区互动等核心功能。

### 1.1 核心业务能力

- **学员端**：课程浏览与搜索、视频在线播放、课程购买、学习进度追踪、评论互动
- **机构/教师端**：课程管理（章节课件）、视频上传与转码、学员管理、订单查看
- **平台管理端**：用户管理、课程审核、订单管理、数据统计、运营配置

### 1.2 设计目标

| 指标 | 目标值 |
|------|--------|
| 并发用户数 | 支持 10,000 在线用户同时学习 |
| 视频播放延迟 | 首帧加载 < 2s（CDN 加速） |
| 接口响应时间 | P99 < 500ms |
| 系统可用性 | 99.9%（月度） |
| 视频转码吞吐 | 单机并行转码 4 路 1080p |

## 2. 技术栈

| 层级 | 技术 | 版本 | 用途 |
|------|------|------|------|
| 后端框架 | Spring Boot | 3.2.x | 应用开发框架 |
| ORM 框架 | MyBatis-Plus | 3.5.5 | 数据库访问，代码生成 |
| 数据库 | MySQL | 8.0 | 业务数据持久化 |
| 缓存 | Redis | 7.2 | 热点数据缓存、分布式锁 |
| 消息队列 | RocketMQ | 5.0 | 异步解耦、转码任务分发 |
| 对象存储 | 阿里云 OSS | - | 视频、图片、课件存储 |
| 视频处理 | FFmpeg | 6.0 | 视频转码、封面截取 |
| 前端框架 | Vue 3 | 3.3.x | 前端 SPA 应用 |
| UI 组件库 | Element Plus | 2.4.x | 后台管理界面 |
| 构建工具 | Vite | 5.0.x | 前端项目构建 |
| 反向代理 | Nginx | 1.24 | 静态资源托管、反向代理 |

## 3. 系统架构图

```
+------------------+       +------------------+       +-----------------------------------+
|    客户端         |       |     Nginx       |       |         Spring Boot 3.2          |
|                  |       |                  |       |                                   |
|  Vue3 SPA        | ----> |  静态文件托管    | ----> |  +-------------+  +-----------+   |
|  (Element Plus)  |       |  反向代理 /api   |       |  | 课程管理模块 |  | 用户服务  |   |
|  H5 / 小程序      |       |  视频请求代理    |       |  +-------------+  +-----------+   |
+------------------+       |  WebSocket       |       |  +-------------+  +-----------+   |
                           +------------------+       |  | 视频处理    |  | 订单支付  |   |
                                                      |  +-------------+  +-----------+   |
                                                      |  +-------------+  +-----------+   |
                                                      |  | 学习追踪    |  | 社区互动  |   |
                                                      |  +-------------+  +-----------+   |
                                                      +-----------------------------------+
                                                              |          |          |          |
                                              +---------------+    +-----+    +-----+    +------+
                                              |                    |              |              |
                                        +-----+-----+      +------+------+  +-----+----+  +----+---+
                                        | MySQL 8.0 |      | Redis 7.2   |  |RocketMQ |  | 阿里云 |
                                        | 3306      |      | 6379        |  | 5.0      |  |  OSS   |
                                        +-----------+      +-------------+  | 9876     |  +--------+
                                                                       +----------+
```

## 4. 模块划分

### 4.1 模块依赖关系

```
edu-common         ← 基础工具、统一响应、常量定义
edu-auth           ← JWT 认证、权限校验（依赖 common）
edu-user           ← 用户注册登录、个人信息管理（依赖 common, auth）
edu-course         ← 课程 CRUD、章节课件管理（依赖 common, auth）
edu-video          ← 视频上传、转码任务（依赖 common, auth, course）
edu-order          ← 订单创建、支付退款（依赖 common, auth, user, course）
edu-learning       ← 学习记录、进度追踪（依赖 common, auth, user, course）
edu-community      ← 评论、问答、笔记（依赖 common, auth, user, course）
edu-admin          ← 后台管理接口（依赖所有业务模块）
edu-gateway        ← 网关层，统一路由与鉴权
```

### 4.2 各模块职责

| 模块 | 职责 | 核心类 |
|------|------|--------|
| edu-common | 统一响应体 Result、分页 PageResult、异常类、工具方法 | `Result.java`, `PageResult.java` |
| edu-auth | JWT 签发/验证、拦截器、权限注解 | `JwtTokenProvider`, `AuthInterceptor` |
| edu-user | 用户注册/登录、信息修改、角色管理 | `UserController`, `UserService` |
| edu-course | 课程/章节/课时的增删改查、分类管理 | `CourseController`, `CourseService` |
| edu-video | 分片上传、转码任务下发、状态查询 | `VideoController`, `TranscodeConsumer` |
| edu-order | 订单创建、支付/退款回调、优惠券核销 | `OrderController`, `PaymentService` |
| edu-learning | 播放进度记录、完课判断、学习统计 | `LearningController`, `LearningService` |
| edu-community | 课程评论、问答、学习笔记 | `CommentController`, `NoteService` |

## 5. 数据库设计概要

### 5.1 核心表清单

| 表名 | 说明 | 预估数据量 |
|------|------|-----------|
| `user` | 用户表（学员、教师、管理员） | 100 万 |
| `course` | 课程主表 | 5 万 |
| `course_chapter` | 课程章节表 | 20 万 |
| `course_lesson` | 课程课时表（关联视频） | 100 万 |
| `order` | 订单主表 | 500 万 |
| `learning_record` | 学习记录表 | 5000 万 |

### 5.2 核心 DDL

```sql
-- 用户表
CREATE TABLE `user` (
    `id`          BIGINT       NOT NULL AUTO_INCREMENT COMMENT '用户主键',
    `username`    VARCHAR(50)  NOT NULL COMMENT '登录用户名',
    `nickname`    VARCHAR(50)  DEFAULT NULL COMMENT '昵称',
    `phone`       VARCHAR(20)  DEFAULT NULL COMMENT '手机号',
    `email`       VARCHAR(100) DEFAULT NULL COMMENT '邮箱',
    `avatar_url`  VARCHAR(500) DEFAULT NULL COMMENT '头像地址',
    `role`        TINYINT      NOT NULL DEFAULT 0 COMMENT '角色: 0-学员 1-教师 2-管理员',
    `status`      TINYINT      NOT NULL DEFAULT 1 COMMENT '状态: 0-禁用 1-正常',
    `created_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`  DATETIME     NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    UNIQUE KEY `uk_username` (`username`),
    UNIQUE KEY `uk_phone` (`phone`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='用户表';

-- 课程主表
CREATE TABLE `course` (
    `id`            BIGINT        NOT NULL AUTO_INCREMENT COMMENT '课程主键',
    `title`         VARCHAR(200)  NOT NULL COMMENT '课程标题',
    `cover_url`     VARCHAR(500)  DEFAULT NULL COMMENT '封面图片地址',
    `description`   TEXT          DEFAULT NULL COMMENT '课程描述',
    `teacher_id`    BIGINT        NOT NULL COMMENT '授课教师ID',
    `category_id`   BIGINT        DEFAULT NULL COMMENT '分类ID',
    `price`         DECIMAL(10,2) NOT NULL DEFAULT 0.00 COMMENT '售价（元）',
    `original_price` DECIMAL(10,2) DEFAULT NULL COMMENT '原价（元）',
    `status`        TINYINT       NOT NULL DEFAULT 0 COMMENT '状态: 0-草稿 1-已上架 2-已下架',
    `student_count` INT           NOT NULL DEFAULT 0 COMMENT '学员数（冗余字段）',
    `rating`        DECIMAL(2,1)  NOT NULL DEFAULT 5.0 COMMENT '评分（1.0~5.0）',
    `chapter_count` INT           NOT NULL DEFAULT 0 COMMENT '章节数（冗余字段）',
    `created_at`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    `updated_at`    DATETIME      NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    PRIMARY KEY (`id`),
    KEY `idx_teacher_id` (`teacher_id`),
    KEY `idx_category_id` (`category_id`),
    KEY `idx_status` (`status`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='课程表';
```

### 5.3 关系型设计

```
course (1) ----< (N) course_chapter (1) ----< (N) course_lesson
                      父子关系                    课时关联视频

order (1) ----< (N) order_item -> course
  一笔订单可包含多个课程

user (1) ----< (N) learning_record
  一个学员多条学习记录

user (1) ----< (N) course_comment
  一条评论属于一个用户和一个课程
```

## 6. 缓存策略

| 缓存对象 | Key 模式 | 过期时间 | 说明 |
|----------|---------|---------|------|
| 课程详情 | `course:detail:{id}` | 30 分钟 | 写入时更新缓存 |
| 课程分类树 | `course:category:tree` | 1 小时 | 分类变更时主动清除 |
| 用户信息 | `user:info:{id}` | 2 小时 | 信息变更时更新 |
| 首页课程列表 | `course:list:home` | 10 分钟 | 上架/下架时清除 |
| 视频播放令牌 | `video:token:{userId}:{lessonId}` | 1 小时 | 防盗链签名 |

## 7. 消息队列设计

| Topic | 消息体 | 消费者 | 用途 |
|-------|-------|--------|------|
| `video-transcode` | `videoId, ossUrl, resolutions` | TranscodeConsumer | 视频转码任务 |
| `video-progress` | `videoId, progress, status` | WebSocket 推送 | 转码进度通知 |
| `order-notify` | `orderId, orderNo, status` | LearningConsumer | 支付成功后发放课程权限 |
| `community-notify` | `commentId, courseId, userId` | NotifyConsumer | 评论/问答通知 |

## 8. 安全设计

- **认证**：JWT Token，Access Token 有效期 2 小时，Refresh Token 有效期 7 天
- **接口鉴权**：`@PreAuthorize` 注解，基于 RBAC 角色控制
- **数据脱敏**：手机号、邮箱在接口返回时部分隐藏（如 138****1234）
- **防重放**：关键接口（支付、下单）使用请求签名 + 时间戳校验
- **防盗链**：OSS 视频资源使用 URL 签名，有效期 1 小时

## 9. 部署架构

```
+--------+     +------------------+     +-----------------+
| 用户    | --> |  CDN / 阿里云OSS  | --> |  视频静态资源     |
+--------+     +------------------+     +-----------------+

+--------+     +--------+     +-----------------------+
| 用户    | --> | Nginx  | --> |  Spring Boot (多实例)  |
+--------+     +--------+     +-----------------------+
                      |
            +---------+---------+---------+
            |         |         |         |
         MySQL     Redis   RocketMQ   OSS
```

生产环境采用 Nginx 做负载均衡，Spring Boot 部署 2~4 个实例，通过 Redis 实现分布式 Session 和分布式锁。
