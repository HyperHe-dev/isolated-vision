# Image Rollout Shim

[English](README.md) | 简体中文

这是一个实验性的 Codex Skill：把本地图片审查交给临时 `codex exec` worker，
只向父任务返回经过校验的纯文本报告，从而避免图片字节、Data URL、base64 和原始
worker 输出进入父任务 rollout。

> [!IMPORTANT]
> 这是一个依赖模型路由的临时方案，不是操作系统沙箱、数据处理保证，也不是
> OpenAI 官方产品。处理敏感材料前请阅读 [SECURITY.md](SECURITY.md)。

## 为什么需要它

本项目用于临时缓解一组 Codex 上游历史与上下文问题：内联图片数据可能被保留，
并在后续轮次、compaction 或传输中再次处理：
[openai/codex#28316](https://github.com/openai/codex/issues/28316)、
[openai/codex#24550](https://github.com/openai/codex/issues/24550)、
[openai/codex#24388](https://github.com/openai/codex/issues/24388) 和
[openai/codex#33024](https://github.com/openai/codex/issues/33024)。

它只能保护那些在像素进入父任务*之前*就通过本 Skill 路由的本地图片，不能清理
已经膨胀的任务，也不是上游问题的正式修复。

本机测试中，简单 worker 调用约 14 秒，父任务到 worker 的隐式流程约 31 秒，
三张图片的 thorough 审查约 69–84 秒。一次包含 90 张历史图片的回放保留了主要
视觉结论，同时纠正了若干过度自信的判断。这些数据仅供参考，不是通用 benchmark。

## 工作方式

1. 父任务根据当前任务生成视觉审查简报。
2. 启动器校验简报与本地路径，必要时生成全图概览和原生分辨率切片。
3. 已完成身份验证的临时 `codex exec --image` worker 执行视觉审查。
4. 启动器丢弃原始 worker 流，只返回通过 schema 校验、不含图片的报告和安全诊断。

父任务决定检查什么以及如何使用证据；worker 只负责视觉分析。

## 安装

需要 macOS 或 Linux、Python 3.10+、Pillow，以及能从 `PATH` 找到且已完成身份验证的
`codex` CLI。嵌套进程还需要能够连接 Codex 服务。

让 Codex 从本仓库安装 Skill 目录：

```text
使用 $skill-installer 安装这个仓库中的 image-rollout-shim 目录。
```

然后把 Python 依赖安装到 Codex 实际使用的同一个 `python3` 环境：

```bash
python3 -m pip install -r /仓库检出目录的绝对路径/image-rollout-shim/requirements.txt
```

也可以手动进行用户级安装：

```bash
mkdir -p ~/.agents/skills
ln -s /仓库检出目录的绝对路径/image-rollout-shim ~/.agents/skills/image-rollout-shim
```

## 使用

```text
使用 $image-rollout-shim 对 /图片的绝对路径/screenshot.png 进行视觉审查。
使用 thorough 模式，重点检查裁切、对齐、排版和视觉回归。
```

默认 worker 模型是 `gpt-5.6-sol`，也可以指定其他模型：

```text
使用 $image-rollout-shim，并让视觉 worker 使用 gpt-5.6-terra 比较这些本地渲染图。
```

本 Skill 允许隐式调用，但 Skill 路由属于模型行为，不是强制工具拦截器。隔离要求
较高时，请显式调用，或者把下面的仓库级规则写入 `AGENTS.md`：

```markdown
每当父任务原本要对绝对本地图片路径调用 `view_image` 时，改用
`$image-rollout-shim`。不要在父任务中读取或发出图片字节。如果 shim 无法运行，
停止这次视觉审查，不要回退到父任务直接看图。
```

## 适用范围与限制

适合 UI 缺陷与视觉回归、修改前后比较、渲染后的文档或仪表盘，以及包含小字的
高分辨率截图。

不太适合对延迟敏感的截图循环、精确像素或色彩测量、隐藏的应用或 3D 状态，
以及已经进入父任务上下文的图片。8 张源图只是协议上限，不是推荐批量：每组只放
语义上必须直接比较的图片，彼此独立的组按顺序处理。

本 Skill 不能拦截所有产图工具、改变服务端数据处理方式、让 worker 使用独立的
操作系统身份，也不能保证结论绝对正确或真正无损。完整边界见
[隔离契约](image-rollout-shim/references/contract.md)。

## 开发与测试

```bash
python3 -m pip install -r image-rollout-shim/requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile image-rollout-shim/scripts/run_isolated_vision.py
```

单元测试使用假的 Codex 可执行文件，不会上传 fixture；GitHub Actions 不运行真实
视觉 worker 测试。

## 许可证

[MIT](LICENSE)
