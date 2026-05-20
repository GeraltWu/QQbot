# Conda 环境与 pip 安装（Python 3.11）

本项目用 **Conda** 做环境隔离，依赖安装统一用 **pip**（与 conda 混装第三方包时更清晰）。

适用于 **Windows**（PowerShell / CMD）。若在 Linux/macOS，激活命令略有不同，见文末。

---

## 1. 前置条件

- 已安装 [Miniconda](https://docs.conda.io/en/latest/miniconda.html) 或 Anaconda，且 `conda` 可在终端中使用。

检查：

```powershell
conda --version
```

---

## 2. 创建环境（Python 3.11）

在项目根目录（例如 `QQbot`）打开终端，执行：

```powershell
conda create -n qqbot python=3.11 -y
```

说明：

- `-n qqbot`：环境名为 `qqbot`，可按需改名。
- `python=3.11`：固定 Python 主版本为 3.11。

---

## 3. 激活环境

### PowerShell / CMD

```powershell
conda activate qqbot
```

验证 Python 版本：

```powershell
python --version
```

应显示 `Python 3.11.x`。

可选：确认当前解释器路径（便于排查是否进错环境）：

```powershell
where python
```

---

## 4. 升级 pip（建议）

在已激活的 `qqbot` 环境中：

```powershell
python -m pip install --upgrade pip
```

---

## 5. 使用 NoneBot 官方 CLI 创建项目（推荐）

脚手架会生成 `pyproject.toml`、`bot.py`、插件目录等；**驱动与适配器**在向导里勾选即可，不必先手写一套目录。

### 5.1 安装 nb-cli（仍在 conda 环境里用 pip）

```powershell
pip install nb-cli
```

若终端里找不到 `nb` 命令，可用模块方式调用（等价）：

```powershell
python -m nb_cli --help
```

### 5.2 新建项目：`nb create`

在**你希望放项目的父目录**下执行（会在下面再建一层项目文件夹）：

```powershell
nb create
```

按向导选择（与当前方案一致即可）：

- **驱动（Driver）**：选 **FastAPI**（多选时通常用空格切换选中，以终端提示为准）
- **适配器（Adapter）**：选 **OneBot V11**（对接 NapCat）

创建完成后进入生成的项目目录，按 CLI 提示安装依赖；常见为（若 `pyproject.toml` 已写好依赖）：

```powershell
cd <你填写的项目目录名>
pip install -e .
```

若向导未自动安装，可在项目根目录手动补装核心包：

```powershell
pip install "nonebot2[fastapi]" nonebot-adapter-onebot
```

确认 `.env` 中驱动为：

```env
DRIVER=~fastapi
```

### 5.3 在已有空目录里初始化：`nb init`

若你已经在 `QQbot` 这类文件夹里，且希望**就在当前目录**生成脚手架，可用：

```powershell
cd d:\OneDrive\learn\projects\QQbot
nb init
```

**注意**：若目录里已有 `.env`、自建文件，向导可能覆盖或冲突；请先备份（例如复制一份 `.env` 到别处），再执行。

### 5.4 启动机器人

在项目根目录（含 `pyproject.toml` / `bot.py` 的那一层）：

```powershell
nb run
```

官方模板里通常不建议直接 `python bot.py` 启动；优先用 `nb run`。

---

## 6. 额外业务依赖（脚手架之外，用 pip）

CLI 创建的是「机器人骨架」；**提醒、Apex 查询**等仍建议按需安装下面这些（仍在激活的 `qqbot` 环境中执行）。

### 6.1 第一阶段常用组合（直接复制）

```powershell
pip install nonebot-plugin-apscheduler
pip install httpx sqlalchemy aiosqlite pydantic-settings python-dotenv
```

说明：

- `nonebot-plugin-apscheduler`：定时任务（自动提醒）
- `httpx`：调用 Apex 第三方 API
- `sqlalchemy` + `aiosqlite`：SQLite 持久化
- `pydantic-settings` + `python-dotenv`：读取 `.env` 配置

也可用 CLI 装商店里的插件（与 pip 二选一即可，勿重复混装同名包）：

```powershell
nb plugin install nonebot-plugin-apscheduler
```

### 6.2 可选增强依赖（按需安装）

```powershell
pip install cachetools tenacity
```

- `cachetools`：短时缓存（减少 Apex API 请求次数）
- `tenacity`：请求失败自动重试

### 6.3 若你维护 requirements.txt（含脚手架 + 业务）

示例（按你实际 `pyproject.toml` 再增减）：

```txt
nonebot2
fastapi
uvicorn
nonebot-adapter-onebot
nonebot-plugin-apscheduler
httpx
sqlalchemy
aiosqlite
pydantic-settings
python-dotenv
cachetools
tenacity
```

安装：

```powershell
pip install -r requirements.txt
```

---

## 7. 可选：在当前环境记录依赖快照

便于备份或另一台机器复现：

```powershell
pip freeze > requirements.txt
```

（注意：`pip freeze` 会列出环境中所有包；若只想维护「直接依赖」，可手写 `requirements.txt` 或配合 pip-tools。）

---

## 8. 退出环境

```powershell
conda deactivate
```

---

## 9. 删除环境（需要重做时）

先退出该环境，再执行：

```powershell
conda env remove -n qqbot -y
```

---

## 附录：Linux / macOS

创建与删除命令相同；激活一般为：

```bash
conda activate qqbot
```

若首次使用 conda 时 shell 未初始化，按 conda 提示执行一次 `conda init` 后重开终端。