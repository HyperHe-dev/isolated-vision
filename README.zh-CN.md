# Image Rollout Shim

[English](README.md) | 简体中文

这是一个实验性的 Codex Skill：把本地图片审查交给临时 `codex exec` worker，
只返回经过校验的纯文本报告。父任务可以接触路径、指令和结论，但不会接触图片
字节、Data URL、base64 或原始 worker 输出。

> [!IMPORTANT]
> 这是一个依赖模型路由的临时方案，不是操作系统沙箱、数据处理保证，也不是
> OpenAI 官方产品。处理敏感材料前请阅读 [SECURITY.md](SECURITY.md)。

## 为什么需要它

本项目用于临时缓解
[openai/codex#28316](https://github.com/openai/codex/issues/28316)、
[#24550](https://github.com/openai/codex/issues/24550)、
[#24388](https://github.com/openai/codex/issues/24388) 和
[#33024](https://github.com/openai/codex/issues/33024) 所涉及的 Codex 历史与上下文
问题。它只能保护在像素进入父任务前就通过本 Skill 路由的本地图片，不能清理已经
膨胀的任务，也不是上游问题的正式修复。

本机测试中，简单 worker 调用约 14 秒，父任务到 worker 的隐式流程约 31 秒，
三图 thorough 审查约 69–84 秒；一次 90 图历史回放保留了主要结论，同时纠正了
若干过度自信的判断。这些数据仅供参考，不是通用 benchmark。

## 工作方式

父任务先根据当前目标编写视觉简报。启动器校验本地路径，必要时生成全图概览和
原生分辨率切片，再启动已完成身份验证的临时 `codex exec --image` worker。
原始 worker 流会被丢弃，父任务只收到通过 schema 校验、不含图片的报告和固定
诊断信息。可选 job ID 支持粗粒度进度查询和终态结果恢复，无需重新审查。

## 安装

需要 macOS 或 Linux、Python 3.10+、Pillow，以及能从 `PATH` 找到且已完成身份
验证的 `codex` CLI。嵌套进程必须能够连接 Codex 服务。

让 Codex 从本仓库安装 Skill 目录：

```text
使用 $skill-installer 安装这个仓库中的 image-rollout-shim 目录。
```

然后把 Pillow 安装到 Codex 实际使用的同一个 `python3` 环境：

```bash
python3 -m pip install -r /仓库检出目录的绝对路径/image-rollout-shim/requirements.txt
```

## 使用

```text
使用 $image-rollout-shim 对 /图片的绝对路径/screenshot.png 进行视觉审查。
使用 thorough 模式，重点检查裁切、对齐、排版和视觉回归。
```

默认 worker 模型是 `gpt-5.6-sol`；需要时可在请求中指定其他模型。

Skill 路由属于模型行为，不是强制工具拦截器。若要在项目内自动路由，请把下面的
规则写入 `AGENTS.md`：

```markdown
每当父任务原本要对绝对本地图片路径调用 `view_image` 时，改用
`$image-rollout-shim`。不要在父任务中读取或发出图片字节。如果 shim 无法运行，
停止这次视觉审查，不要回退到父任务直接看图。
```

确有展示价值时，父任务可以向用户提供稳定原图的普通文件链接，但不得嵌入图片
语法或暴露 worker 的私有临时文件。

## 适用范围

- 适合：UI 回归、修改前后比较、渲染后的文档或仪表盘，以及包含小细节的高分辨率
  截图。
- 不适合：对延迟敏感的循环、精确像素或色彩测量、隐藏的应用或 3D 状态，以及已经
  进入父任务上下文的图片。
- 本 Skill 不能拦截所有产图工具，也不保证结论完全正确或真正无损。8 张源图只是
  协议上限，不是推荐批量。

完整协议见[隔离契约](image-rollout-shim/references/contract.md)，信任边界见
[SECURITY.md](SECURITY.md)。

## 开发与测试

```bash
python3 -m pip install -r image-rollout-shim/requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile image-rollout-shim/scripts/run_isolated_vision.py
```

单元测试使用假的 Codex 可执行文件，不会上传 fixture；GitHub Actions 不运行真实
视觉 worker。

## 许可证

[MIT](LICENSE)
