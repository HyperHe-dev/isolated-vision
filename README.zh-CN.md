# Isolated Vision

[English](README.md) | 简体中文

这是一个实验性的 Codex Skill：把本地图片通过临时 `codex exec` worker 交给模型
查看，并向父任务返回经过校验的纯文本报告。父任务根据图片路径、任务上下文和文字
视觉信息继续工作。

> [!IMPORTANT]
> 这是一个依赖模型路由的临时方案，不是操作系统沙箱、数据处理保证，也不是
> OpenAI 官方产品。处理敏感材料前请阅读 [SECURITY.md](SECURITY.md)。

## 为什么需要它

本项目用于临时缓解
[openai/codex#28316](https://github.com/openai/codex/issues/28316)、
[#24550](https://github.com/openai/codex/issues/24550)、
[#24388](https://github.com/openai/codex/issues/24388) 和
[#33024](https://github.com/openai/codex/issues/33024) 所记录的图像历史与大上下文
故障。本机使用 Codex CLI `0.150.1` 仍可复现 WebSocket 连接问题，图片进入父任务
上下文是触发该问题的显著因素。此次 CLI 更新前，图片内容会在上下文压缩后被清理。

本 Skill 只能保护在像素进入父任务前就通过它路由的本地图片，不能清理已经膨胀的
任务，也不是上游问题的正式修复。

本机测试中，简单 worker 调用约 14 秒，父任务到 worker 的隐式流程约 31 秒，
自动准备细节的三图任务约 69–84 秒；一次 90 图历史回放保留了主要结论，同时
纠正了若干过度自信的判断。这些数据仅供参考，不是通用 benchmark。

## 工作方式

父任务提供本地图片的绝对路径和简短的看图目的。启动器校验源文件，为每张图片
生成完整概览，为高分辨率图片增加原生分辨率细节切片，然后启动已完成身份验证的
临时 `codex exec --image` worker。原始 worker 流会被丢弃，父任务只收到通过
schema 校验的文字报告和固定诊断信息。可选 job ID 支持粗粒度进度查询和终态结果
恢复，无需重新启动视觉任务。

## 安装

需要 macOS 或 Linux、Python 3.10+、Pillow，以及能从 `PATH` 找到且已完成身份
验证的 `codex` CLI。嵌套进程必须能够连接 Codex 服务。

让 Codex 从本仓库安装 Skill 目录：

```text
使用 $skill-installer 安装这个仓库中的 isolated-vision 目录。
```

然后把 Pillow 安装到 Codex 实际使用的同一个 `python3` 环境：

```bash
python3 -m pip install -r /仓库检出目录的绝对路径/isolated-vision/requirements.txt
```

## 使用

```text
使用 $isolated-vision 查看 /图片的绝对路径/screenshot.png，并返回当前任务需要的视觉信息。
```

图片准备会自动完成。当任务明确需要每张受支持的原图只附加一次时，可以使用
`--original-only`。默认 worker 模型是 `gpt-5.6-sol`；需要时可通过 `--model`
选择其他模型。

Skill 路由属于模型行为，不是强制工具拦截器。若要在项目内自动路由，请把下面的
规则写入 `AGENTS.md`：

```markdown
当任务需要从绝对本地图片路径获取视觉信息时，通过 `$isolated-vision` 路由这些
路径，并根据返回的文字观察继续工作。父任务中的图片路由保持为路径传递。
```

处理过程中，父任务可以在适合时用 Markdown 图片链接展示稳定原图。Codex UI
负责渲染预览，worker 的私有临时文件仍留在隔离路径中。

## 适用范围

- 适合：UI 反馈、修改前后比较、渲染后的文档或仪表盘、3D 渲染，以及包含小细节
  的高分辨率截图。
- 不适合：对延迟敏感的循环、精确像素或色彩测量、隐藏的应用或 3D 状态，以及已经
  进入父任务上下文的图片。
- 自动生成的完整概览和原生分辨率切片用于保留有用的视觉细节，但模型感知不等同
  于精确像素或色彩测量。一次请求最多包含 8 张源图和 48 个私有附件。

完整协议见[隔离契约](isolated-vision/references/contract.md)，信任边界见
[SECURITY.md](SECURITY.md)。

## 开发与测试

```bash
python3 -m pip install -r isolated-vision/requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile isolated-vision/scripts/vision.py
```

单元测试使用假的 Codex 可执行文件，不会上传 fixture；GitHub Actions 不运行真实
视觉 worker。

## 许可证

[MIT](LICENSE)
