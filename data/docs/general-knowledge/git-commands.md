# Git 仓库常用命令参考

> **适用场景**：团队协作开发、版本管理、分支策略
> **Git 版本**：2.40+
> **最后更新**：2026-07-20

---

## 1. 仓库初始化与克隆

### 1.1 初始化新仓库

```bash
git init
```

在当前目录创建一个新的 Git 仓库，生成 `.git` 隐藏文件夹。初始化后需要添加远程仓库：

```bash
git remote add origin https://github.com/your-org/your-repo.git
```

### 1.2 克隆远程仓库

```bash
# HTTPS 方式（无需配置 SSH）
git clone https://github.com/your-org/your-repo.git

# SSH 方式（需先配置 SSH Key）
git clone git@github.com:your-org/your-repo.git

# 克隆指定分支
git clone -b develop https://github.com/your-org/your-repo.git

# 浅克隆（只拉取最近一次提交，节省空间）
git clone --depth=1 https://github.com/your-org/your-repo.git
```

### 1.3 查看远程仓库

```bash
git remote -v                    # 查看所有远程仓库及其 URL
git remote show origin          # 查看远程仓库详细信息
git remote set-url origin <新URL>  # 修改远程仓库地址
```

---

## 2. 日常工作流

### 2.1 查看状态与差异

```bash
git status                      # 查看工作区状态（已修改/已暂存/未跟踪）
git status -s                   # 简短输出
git diff                        # 查看工作区与暂存区的差异
git diff --staged               # 查看暂存区与最新提交的差异
git diff HEAD~1                 # 查看与上一次提交的差异
```

### 2.2 添加与提交

```bash
# 添加单个文件
git add src/main.py

# 添加所有修改的文件（不包含新文件）
git add -u

# 添加所有变更（包含新文件、修改、删除）
git add -A

# 交互式添加（逐个文件确认）
git add -p

# 提交暂存区的内容
git commit -m "feat: 新增用户登录功能"

# 修改上一次提交（不产生新 commit 记录）
git commit --amend -m "feat: 新增用户登录功能（含参数校验）"

# 跳过暂存区，直接提交所有已跟踪文件的修改
git commit -am "fix: 修复空指针异常"
```

### 2.3 提交信息规范

项目采用 Conventional Commits 规范：

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feat:` | 新功能 | `feat: 新增设备批量导入接口` |
| `fix:` | 修复 Bug | `fix: 修复 TDengine 查询超时问题` |
| `docs:` | 文档变更 | `docs: 更新 API 接口文档` |
| `style:` | 代码格式（不影响逻辑） | `style: 统一缩进为 4 空格` |
| `refactor:` | 重构 | `refactor: 抽取预警规则引擎为独立模块` |
| `test:` | 测试 | `test: 新增预警规则单元测试` |
| `chore:` | 构建/工具 | `chore: 升级 Spring Boot 到 3.2.0` |
| `perf:` | 性能优化 | `perf: 批量写入优化，提升 3 倍吞吐` |

---

## 3. 分支管理

### 3.1 分支基础操作

```bash
git branch                      # 列出本地分支
git branch -a                   # 列出所有分支（含远程）
git branch <branch-name>        # 创建新分支
git checkout -b <branch-name>   # 创建并切换到新分支
git switch <branch-name>       # 切换到已有分支（Git 2.23+）
git branch -d <branch-name>     # 删除已合并的分支
git branch -D <branch-name>     # 强制删除分支（即使未合并）
```

### 3.2 分支策略

项目采用以下分支模型：

```
main          # 生产分支，只接受 PR 合入
develop       # 开发分支，日常开发在此进行
feature/*     # 功能分支，从 develop 拉出，完成后合回 develop
hotfix/*      # 紧急修复分支，从 main 拉出，修复后合回 main 和 develop
release/*     # 发布分支，从 develop 拉出，测试通过后合回 main
docs/*        # 文档分支，文档更新专用
```

### 3.3 合并与变基

```bash
# 将 feature 分支合并到当前分支
git merge feature/device-import

# 变基（将当前分支的提交重新应用到目标分支之上）
git rebase develop

# 交互式变基（可合并、修改、删除、重排提交）
git rebase -i HEAD~3

# 变基冲突后继续
git rebase --continue

# 放弃变基
git rebase --abort
```

> **注意**：已推送到远程的分支不要 rebase，否则会导致协作者的历史混乱。

---

## 4. 远程同步

### 4.1 推送与拉取

```bash
# 推送当前分支到远程
git push origin feature/device-import

# 首次推送并设置上游跟踪
git push -u origin feature/device-import

# 强制推送（覆盖远程，慎用！）
git push --force origin feature/device-import

# 拉取远程更新并合并
git pull origin develop

# 拉取远程更新并变基（推荐，保持线性历史）
git pull --rebase origin develop

# 获取远程更新但不合并
git fetch origin
```

### 4.2 跟踪分支

```bash
# 查看跟踪关系
git branch -vv

# 设置当前分支跟踪远程分支
git branch --set-upstream-to=origin/develop develop

# 删除远程分支
git push origin --delete feature/old-feature
```

---

## 5. 撤销与回退

### 5.1 撤销工作区修改

```bash
# 撤销单个文件的修改（恢复到暂存区状态）
git checkout -- src/main.py

# 撤销所有工作区的修改
git checkout .

# 新版 Git 推荐用法
git restore src/main.py
git restore .
```

### 5.2 撤销暂存

```bash
# 将文件从暂存区移回工作区
git reset HEAD src/main.py

# 新版 Git 推荐用法
git restore --staged src/main.py
```

### 5.3 回退提交

```bash
# 软回退：撤销提交，保留修改在暂存区
git reset --soft HEAD~1

# 混合回退：撤销提交和暂存，保留修改在工作区（默认）
git reset --mixed HEAD~1

# 硬回退：撤销提交、暂存和工作区修改（不可恢复！）
git reset --hard HEAD~1

# 安全回退：创建一个新提交来撤销（不改变历史）
git revert <commit-hash>

# 回退多个提交
git revert <hash1> <hash2> <hash3>
```

> **团队协作中优先使用 `git revert`**，因为它不会改写历史，不会影响其他协作者。

---

## 6. 暂存工作进度

```bash
# 暂存当前修改
git stash

# 暂存并添加说明
git stash push -m "正在开发预警模块，切换到 hotfix"

# 查看暂存列表
git stash list

# 恢复最近一次暂存
git stash pop

# 恢复指定暂存
git stash apply stash@{2}

# 删除暂存
git stash drop stash@{0}

# 清空所有暂存
git stash clear
```

---

## 7. 标签管理

```bash
# 创建轻量标签
git tag v2.1.0

# 创建带注释的标签（推荐，包含作者、日期、说明）
git tag -a v2.1.0 -m "v2.1.0: 新增预警系统、MQTT协议优化"

# 给历史提交打标签
git tag -a v2.0.1 <commit-hash> -m "紧急修复 TDengine 连接池泄漏"

# 推送标签到远程
git push origin v2.1.0

# 推送所有标签
git push origin --tags

# 查看标签
git tag -l

# 查看标签详情
git show v2.1.0

# 删除标签
git tag -d v2.1.0                    # 删除本地
git push origin --delete v2.1.0       # 删除远程
```

---

## 8. 日志与搜索

```bash
# 查看提交日志
git log

# 简洁单行显示
git log --oneline

# 图形化显示分支历史
git log --oneline --graph --all

# 查看某个文件的修改历史
git log --follow src/main.py

# 搜索提交信息
git log --grep="预警" --oneline

# 查看某个提交的详细内容
git show <commit-hash>

# 查看某个文件在某次提交中的内容
git show <commit-hash>:src/main.py

# 查找引入 Bug 的提交（二分法定位）
git bisect start
git bisect bad                    # 当前版本有 Bug
git bisect good v2.0.0            # 该版本正常
git bisect reset                  # 结束定位
```

---

## 9. .gitignore 配置

项目 `.gitignore` 推荐配置：

```gitignore
# 编译输出
*.class
*.jar
*.war
target/
build/

# Python
__pycache__/
*.pyc
.venv/
*.egg-info/
dist/

# IDE
.idea/
.vscode/
*.iml

# 环境配置（含敏感信息）
.env
.env.local

# 系统文件
.DS_Store
Thumbs.db

# 数据目录
 data/chroma_db/
data/bm25_index/
data/model_cache/

# 日志
*.log
logs/
```

---

## 10. 常见问题处理

### 10.1 合并冲突

```bash
# 1. 查看冲突文件
git status

# 2. 手动编辑冲突文件，解决标记
# <<<<<<< HEAD
# 你的代码
# =======
# 他们的代码
# >>>>>>> feature/xxx

# 3. 标记为已解决
git add <resolved-file>

# 4. 完成合并
git commit -m "merge: 解决与 feature/xxx 的冲突"
```

### 10.2 误删分支恢复

```bash
# 查看最近删除的提交
git reflog

# 找到被删分支的最后一次提交 hash，然后恢复
git branch <branch-name> <commit-hash>
```

### 10.3 清理无用分支和对象

```bash
# 删除所有已合并到 main 的本地分支
git branch --merged main | grep -v "^\*\|  main" | xargs git branch -d

# 清理远程已删除的分支引用
git fetch --prune

# 清理无用对象，释放磁盘空间
git gc --prune=now
```
