# Project A — 视频转码子系统设计文档

> 版本：v1.0.0 | 更新日期：2026-07-28 | 涉及组件：FFmpeg 6.0 + RocketMQ 5.0 + 阿里云 OSS

## 1. 系统概述

视频转码子系统是在线教育平台的核心基础服务之一，负责教师上传视频后的格式转换、多分辨率输出、封面截取等处理工作。通过 **RocketMQ 异步解耦** 上传与转码，利用 **FFmpeg** 完成实际的转码计算，最终将转码产物上传至 **阿里云 OSS** 供学员播放。

### 1.1 设计目标

| 指标 | 目标 |
|------|------|
| 支持输入格式 | MP4, MOV, AVI, MKV, FLV |
| 输出格式 | MP4 (H.264 + AAC) |
| 输出分辨率 | 1080p / 720p / 480p 三档 |
| 单路转码耗时 | < 视频时长的 1/3（使用 medium preset） |
| 并行转码能力 | 单机 4 路 1080p 并行 |
| 转码成功率 | > 99.5%（含重试） |

## 2. 转码流程

```
+--------+    1.分片上传    +-------+    2.合并文件     +---------+
|  前端   | ------------> |  后端  | ------------> |  OSS    |
| (Vue3) | <------------ | Spring | <------------ | 原始视频 |
+--------+    返回uploadId +-------+    确认完成     +---------+
                                        |
                                        | 3.发送MQ消息
                                        v
                                  +-------------+
                                  |  RocketMQ   |
                                  |  Topic:      |
                                  | video-transcode |
                                  +-------------+
                                        |
                                        | 4.消费者拉取
                                        v
                                  +-------------+
                                  | Transcode   |
                                  | Consumer    |
                                  +-------------+
                                   |     |     |
                                   |     | 5a.下载视频到本地临时目录
                                   |     | 5b.FFmpeg多分辨率转码
                                   |     | 5c.截取封面图
                                   |     |
                                   |     | 6.上传转码产物到OSS
                                   |     v
                                   | +---------+
                                   | |   OSS   |
                                   | |转码视频+ |
                                   | |封面图片  |
                                   | +---------+
                                   |
                                   | 7.更新数据库状态
                                   | 8.发送进度完成消息
                                   v
                                  +-------------+
                                  | RocketMQ    |
                                  | Topic:      |
                                  | video-progress |
                                  +-------------+
                                        |
                                   9. WebSocket推送给前端
```

### 2.1 流程详解

1. **分片上传**：前端将视频文件分为 5MB 的分片，通过 `POST /videos/upload` 逐片上传到后端
2. **合并文件**：后端调用 OSS `CompleteMultipartUpload` API 合并所有分片，生成完整原始视频
3. **发送 MQ 消息**：后端向 `video-transcode` Topic 发送转码任务消息
4. **消费消息**：TranscodeConsumer 从 RocketMQ 拉取消息，开始转码流程
5. **本地转码**：下载原始视频到临时目录，使用 FFmpeg 执行多分辨率转码和封面截取
6. **上传产物**：将转码后的视频文件和封面图上传到 OSS
7. **更新状态**：更新数据库中视频记录的状态、OSS 地址、时长等信息
8. **进度通知**：向 `video-progress` Topic 发送完成消息
9. **前端推送**：WebSocket 服务消费进度消息，实时推送给教师前端页面

## 3. FFmpeg 转码命令

### 3.1 多分辨率转码

1080p 转码（码率 2.5Mbps）：

```bash
ffmpeg -i input.mp4 \
  -c:v libx264 -preset medium -crf 23 \
  -vf "scale=1920:1080" \
  -b:v 2500k -maxrate 2750k -bufsize 5000k \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  output_1080p.mp4
```

720p 转码（码率 1.5Mbps）：

```bash
ffmpeg -i input.mp4 \
  -c:v libx264 -preset medium -crf 23 \
  -vf "scale=1280:720" \
  -b:v 1500k -maxrate 1650k -bufsize 3000k \
  -c:a aac -b:a 128k \
  -movflags +faststart \
  output_720p.mp4
```

480p 转码（码率 0.8Mbps）：

```bash
ffmpeg -i input.mp4 \
  -c:v libx264 -preset medium -crf 23 \
  -vf "scale=854:480" \
  -b:v 800k -maxrate 880k -bufsize 1600k \
  -c:a aac -b:a 96k \
  -movflags +faststart \
  output_480p.mp4
```

### 3.2 转码参数配置表

| 参数 | 1080p | 720p | 480p |
|------|-------|------|------|
| 分辨率 | 1920x1080 | 1280x720 | 854x480 |
| 视频码率 | 2500 kbps | 1500 kbps | 800 kbps |
| 最大码率 | 2750 kbps | 1650 kbps | 880 kbps |
| 缓冲区 | 5000 kbps | 3000 kbps | 1600 kbps |
| 编码器 | libx264 | libx264 | libx264 |
| Preset | medium | medium | medium |
| CRF | 23 | 23 | 23 |
| 音频码率 | 128 kbps | 128 kbps | 96 kbps |
| 音频编码 | AAC | AAC | AAC |

### 3.3 封面截取

从视频第 5 秒截取一帧作为封面图：

```bash
ffmpeg -ss 00:00:05 -i input.mp4 -vframes 1 -q:v 2 cover.jpg
```

参数说明：
- `-ss 00:00:05`：定位到第 5 秒（seek 到关键帧附近，速度较快）
- `-vframes 1`：仅输出 1 帧
- `-q:v 2`：JPEG 质量 2（范围 2~31，越小质量越高）
- 输出尺寸自动继承源视频分辨率，前端展示时通过 CSS 缩放

## 4. 分片上传设计

### 4.1 前端分片策略

| 配置项 | 值 | 说明 |
|--------|---|------|
| 分片大小 | 5 MB (5242880 字节) | 平衡并发数和单次传输效率 |
| 并发上传数 | 3 | 同时上传 3 个分片 |
| 重试次数 | 3 | 单个分片上传失败重试 3 次 |
| 支持断点续传 | 是 | 记录已上传分片的 ETag |

### 4.2 后端处理流程

```java
// 伪代码：分片上传核心逻辑
public UploadResult uploadChunk(MultipartFile file, String uploadId,
                                  int chunkIndex, int totalChunks) {
    // 1. 校验 uploadId 有效性（Redis 中维护上传会话）
    String sessionKey = "upload:session:" + uploadId;
    UploadSession session = redisTemplate.opsForValue().get(sessionKey);

    // 2. 上传分片到 OSS
    OSS client = ossClientFactory.getClient();
    UploadPartRequest request = new UploadPartRequest(
        bucketName, objectName, uploadId, chunkIndex + 1,
        file.getInputStream(), file.getSize()
    );
    UploadPartResult result = client.uploadPart(request);

    // 3. 记录分片 ETag（Redis 有序集合）
    redisTemplate.opsForZSet().add(
        "upload:parts:" + uploadId,
        result.getETag(), chunkIndex
    );

    // 4. 判断是否所有分片已上传完毕
    long uploadedCount = redisTemplate.opsForZSet()
        .zCard("upload:parts:" + uploadId);
    if (uploadedCount == totalChunks) {
        return completeMultipartUpload(uploadId, objectName);
    }
    return new UploadResult(uploadId, chunkIndex, false, result.getETag());
}
```

### 4.3 文件合并

```java
// 伪代码：OSS 分片合并
public VideoInfo completeMultipartUpload(String uploadId, String objectName) {
    OSS client = ossClientFactory.getClient();
    List<PartETag> parts = getPartETags(uploadId);

    CompleteMultipartUploadRequest request =
        new CompleteMultipartUploadRequest(bucketName, objectName, uploadId, parts);
    client.completeMultipartUpload(request);

    // 更新视频记录状态为 PENDING，发送转码消息
    videoMapper.updateStatus(videoId, "PENDING");
    rocketMQTemplate.convertAndSend("video-transcode",
        new TranscodeMessage(videoId, objectName));

    // 清理 Redis 临时数据
    redisTemplate.delete("upload:session:" + uploadId);
    redisTemplate.delete("upload:parts:" + uploadId);
}
```

## 5. 转码进度回调

### 5.1 进度上报机制

TranscodeConsumer 通过定时轮询 FFmpeg 进程的标准输出来获取转码进度：

```java
// 伪代码：解析 FFmpeg 进度
Process process = Runtime.getRuntime().exec(ffmpegCmd);
BufferedReader reader = new BufferedReader(
    new InputStreamReader(process.getErrorStream())
);

String line;
while ((line = reader.readLine()) != null) {
    // FFmpeg 输出格式：frame=  120 fps=25 q=23.0 size=    1024kB time=00:00:05.00
    if (line.contains("time=")) {
        String timeStr = parseTime(line);
        double progress = calculateProgress(timeStr, totalDuration);
        // 发送进度消息到 RocketMQ
        rocketMQTemplate.convertAndSend("video-progress",
            new ProgressMessage(videoId, progress, "TRANSCODING"));
    }
}
```

### 5.2 WebSocket 实时推送

前端通过 WebSocket 连接后端，后端消费 `video-progress` 消息并推送给对应教师：

```
前端连接: ws://localhost:8080/ws/transcode?videoId=5001
服务端推送: {"videoId":5001, "progress":65, "status":"TRANSCODING"}
```

## 6. 防盗链策略

### 6.1 OSS Referer 白名单

在阿里云 OSS 控制台配置 Bucket 的防盗链规则：

| 配置项 | 值 |
|--------|---|
| 防盗链类型 | 白名单 |
| 允许空 Referer | 否 |
| 白名单域名 | `*.edu-platform.com`, `localhost` |

### 6.2 URL 签名

后端生成带签名的临时访问 URL，有效期 1 小时：

```java
// 伪代码：生成签名 URL
public String generateSignedUrl(String objectKey) {
    OSS client = ossClientFactory.getClient();
    Date expiration = new Date(System.currentTimeMillis() + 3600 * 1000);
    GeneratePresignedUrlRequest request =
        new GeneratePresignedUrlRequest(bucketName, objectKey, HttpMethod.GET);
    request.setExpiration(expiration);
    URL signedUrl = client.generatePresignedUrl(request);
    return signedUrl.toString();
}
```

前端播放器使用签名 URL 请求视频：
```
https://edu-oss.oss-cn-beijing.aliyuncs.com/videos/720p/5001.mp4
  ?OSSAccessKeyId=LTAI5tXXX
  &Signature=abc123def456
  &Expires=1722167622
```

## 7. 异常处理

### 7.1 重试策略

| 场景 | 重试策略 | 说明 |
|------|---------|------|
| 分片上传失败 | 重试 3 次，间隔 2s/4s/8s（指数退避） | 网络抖动导致 |
| FFmpeg 进程异常退出 | 重试 3 次 | 磁盘 IO 或内存不足 |
| OSS 上传转码产物失败 | 重试 3 次 | 网络问题 |
| 超过最大重试次数 | 标记视频状态为 FAILED | 通知运营人员 |

### 7.2 失败通知

转码失败后通过 RocketMQ 发送告警消息到运维系统：

```java
// 转码失败处理
@RetryableTopic(
    topics = "video-transcode",
    dlqTopicSuffix = ".dlq",
    maxAttempts = 3,
    backOff = @BackOff(delay = 5000, multiplier = 2)
)
public void processTranscode(TranscodeMessage message) {
    try {
        doTranscode(message);
    } catch (Exception e) {
        log.error("转码失败: videoId={}, attempt={}", message.getVideoId(), e);
        // 最终失败后标记数据库状态
        videoMapper.updateStatus(message.getVideoId(), "FAILED");
        // 发送告警通知
        notifyService.alert("视频转码失败", "videoId=" + message.getVideoId());
        throw e; // 抛出异常触发 RocketMQ 重试
    }
}
```

### 7.3 临时文件清理

转码过程中产生的本地临时文件需及时清理：

```java
// 转码完成后的清理操作
finally {
    // 删除下载的原始视频
    Files.deleteIfExists(Paths.get(tempInputPath));
    // 删除转码产物（已上传到 OSS）
    Files.deleteIfExists(Paths.get(tempOutput1080p));
    Files.deleteIfExists(Paths.get(tempOutput720p));
    Files.deleteIfExists(Paths.get(tempOutput480p));
    Files.deleteIfExists(Paths.get(tempCoverPath));
    // 删除临时工作目录
    Files.deleteIfExists(Paths.get(tempWorkDir));
}
```

## 8. 存储目录规范

OSS Bucket 中的文件组织结构：

```
edu-oss/
  +-- videos/
  |     +-- raw/          # 原始上传视频（转码后可选删除）
  |     +-- 1080p/        # 1080p 转码产物
  |     +-- 720p/          # 720p 转码产物
  |     +-- 480p/          # 480p 转码产物
  +-- covers/              # 视频封面图
  +-- avatars/             # 用户头像
  +-- courseware/          # 课程课件附件
```

文件命名规则：`{videoId}.mp4`（如 `5001.mp4`），封面图 `cover_{videoId}.jpg`
