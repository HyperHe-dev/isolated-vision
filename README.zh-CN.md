# Image Rollout Shim

[English](README.md) | 简体中文

这是一个实验性的 Codex Skill：把本地图片审查交给临时
`codex exec` 视觉 worker，并且只向父任务返回经过校验的纯文本报告。

它解决的问题非常具体：当父任务原本要对绝对本地路径调用
`view_image` 时，避免让图片内容、Data URL、base64 或原始 worker 输出进入
父任务 rollout。

> [!IMPORTANT]
> 这是一个依赖模型正确路由的 rollout 隔离临时方案，不是操作系统沙箱、
> 数据处理保证，也不是 OpenAI 官方产品。处理敏感材料前请阅读
> [SECURITY.md](SECURITY.md)。

## 工作方式

1. 父任务根据当前任务和已启用的领域 Skill 生成视觉审查简报。
2. 启动器校验简报和本地图片路径。
3. 在 `thorough` 模式下，启动器会在私有临时目录中生成全图概览；必要时再生成
   带重叠区域的原生分辨率切片。
4. 已完成身份验证的临时 `codex exec --image` worker 审查这些图片。
5. 启动器丢弃 worker 的 stdout 和 stderr，校验最终 JSON，拒绝任何疑似图片的
   输出，最后只返回文本报告和安全元数据。

父任务仍负责决定看什么、关注什么，以及如何使用审查结论。Worker 只负责提供
视觉证据。

## 测试表现与适用问题

在作者的本机测试环境中，简单图片直接调用视觉 worker 约需 14 秒；包含父任务
隐式路由的完整流程约需 31 秒。一次私有历史回放把 90 个图片输入分成 13 批完成
审查，复现了主要视觉结论，同时纠正了若干过度自信的判断。端到端 smoke test
中，父任务 JSONL 内的 `input_image`、Data URL 和 base64 标记数量均为零。这些
数字只是本机观测结果，不是可迁移的性能 benchmark；实际耗时会受到模型、网络、
图片数量与分辨率以及审查要求的影响。

比较适合处理：

- UI 裁切、重叠、间距、对齐、排版、对比度和视觉回归；
- 修改前后截图比较，以及连续的渲染结果审查；
- 已经保存为本地图片的 PDF、文档、幻灯片或仪表盘页面；
- 需要通过“全图概览 + 原生分辨率切片”检查的小字或高分辨率截图；
- 可以只保存到本地路径、而不向父任务返回像素的浏览器或 Computer Use 截图。

不太适合对延迟敏感的连续截图循环、精确像素或色度测量、隐藏的应用状态或
3D 场景状态，以及已经进入父任务上下文的图片。测试中并发启动多个嵌套 worker
的稳定性较差，因此优先把最多 8 张源图放进一次批量调用，或者按顺序执行。

## 环境要求

- macOS 或 Linux
- Python 3.10 或更高版本
- 用于本地图片解码和切片的 [Pillow](https://python-pillow.org/)
- 已完成身份验证并且能从 `PATH` 找到的 `codex` CLI
- 可以创建私有临时目录
- 父任务运行环境允许嵌套 Codex 进程连接服务

默认 worker 模型是 `gpt-5.6-sol`。调用方也可以传入另一个经过单值校验的
模型标识符。

## 安装

从 GitHub 仓库安装时，可以直接告诉 Codex：

```text
使用 $skill-installer 安装这个仓库中的 image-rollout-shim 目录。
```

请把 Python 依赖安装到 Codex 实际调用的同一个 `python3` 环境：

```bash
python3 -m pip install -r /仓库检出目录的绝对路径/image-rollout-shim/requirements.txt
```

手动安装到当前用户时，可以把 Skill 复制或链接到 Codex 用户 Skill 目录：

```bash
mkdir -p ~/.agents/skills
ln -s /仓库检出目录的绝对路径/image-rollout-shim ~/.agents/skills/image-rollout-shim
```

Codex 通常会自动检测 Skill 变化。如果没有出现，请重启 Codex。

## 使用

显式调用：

```text
使用 $image-rollout-shim 对 /图片的绝对路径/screenshot.png 进行视觉审查。
使用 thorough 模式，重点检查裁切、对齐、排版和视觉回归。
```

指定模型：

```text
使用 $image-rollout-shim，并让视觉 worker 使用 gpt-5.6-terra 比较这些本地渲染图。
```

本 Skill 已允许隐式调用，因此当 Codex 原本准备使用 `view_image` 检查本地图片时，
它可能会自动选择本 Skill。但隐式 Skill 路由属于模型行为，并不是强制工具拦截器。
当隔离要求很重要时，建议显式调用。

如果希望在某个仓库内强化路由，又不想安装 Hook，可以把下面的内容加入该仓库的
`AGENTS.md`：

```markdown
每当父任务原本要对绝对本地图片路径调用 `view_image` 时，改用
`$image-rollout-shim`。不要在父任务中读取或发出图片字节。如果 shim 无法运行，
停止这次视觉审查，不要回退到父任务直接看图。
```

## 直接测试启动器

正常情况下，Skill 会自行调用启动器。也可以用下面的方式直接测试：

```bash
python3 image-rollout-shim/scripts/run_isolated_vision.py \
  --image /图片的绝对路径/image.png <<'JSON'
{
  "objective": "描述可见布局并找出明显的视觉缺陷。",
  "context": "本地 smoke test。",
  "focus": ["布局", "可读性", "视觉缺陷"],
  "questions": ["是否存在元素被裁切或互相重叠？"],
  "mode": "thorough",
  "output_language": "简体中文"
}
JSON
```

成功时，stdout 只包含一个 JSON 对象，其中包括 `status: "ok"`、结构化
`report` 和不含图片的元数据。错误同样是稳定、安全的 JSON，并且不会包含
原始子进程输出。

## 边界与限制

本项目不能：

- 移除已经通过用户附件、`view_image`、Computer Use、浏览器截图或其他图片工具
  进入父任务的像素；
- 自动拦截所有可能产生图片的工具调用；
- 改变 OpenAI 服务端的数据处理或保留方式；
- 让 worker 使用独立的操作系统身份；
- 保证视觉结论绝对正确或真正无损。

完整说明请阅读[隔离契约](image-rollout-shim/references/contract.md)。

## 开发与测试

```bash
python3 -m pip install -r image-rollout-shim/requirements.txt
python3 -m unittest discover -s tests -p 'test_*.py' -v
python3 -m py_compile image-rollout-shim/scripts/run_isolated_vision.py
```

单元测试使用假的 Codex 可执行文件，不会上传测试图片，也不需要身份验证。
GitHub Actions 不会执行真实视觉 worker 测试。

## 许可证

[MIT](LICENSE)
