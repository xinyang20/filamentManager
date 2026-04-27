# Bambu Lab 本地 MQTT 后端开发指南

本文档只描述后端系统应如何通过用户显式配置连接 Bambu Lab 打印机、订阅本地 MQTT、解析打印状态和 AMS 耗材数据。本文档不得包含任何本地机器、测试打印机、访问码、样本文件路径或 Bambu Studio 本机配置路径。

后端实现原则：

- 后端只能使用用户在系统配置中显式保存的 `host`、`serial`、`access_code` 等连接参数。
- 后端代码不能从开发者本机脚本、样本 JSONL、Bambu Studio 配置文件、截图或历史测试文件中推断连接信息。
- 本地测试信息只允许放在独立的本地测试文档中，不能作为后端运行时配置来源。
- 所有 MQTT 原始 payload 应保留，字段语义不确定时先兼容存储，再通过后续测试补充映射。

## 连接模型

Bambu 打印机在局域网内暴露 MQTT over TLS 服务。AMS 数据通过打印机上报，不是 AMS 自身直接提供网络接口。

```text
backend service -> printer host:8883 -> MQTT report topic -> print/AMS payload
```

连接参数：

| 参数 | 说明 |
|---|---|
| `host` | 打印机局域网 IP 或可解析主机名，必须由用户配置 |
| `port` | MQTT TLS 端口，通常为 `8883` |
| `serial` | 打印机序列号，用于 MQTT topic |
| `username` | 固定使用 `bblp` |
| `password` | 打印机 LAN access code，必须由用户配置 |
| `tls` | 必须启用 |
| `certificate_verify` | 当前实践通常不校验证书；如启用校验需处理打印机自签/私有证书 |
| `client_id` | 后端生成的唯一客户端 ID |
| `keepalive` | 建议 60 秒 |

订阅 topic：

```text
device/<serial>/report
```

请求 topic：

```text
device/<serial>/request
```

请求完整状态快照：

```json
{
  "pushing": {
    "sequence_id": "backend-generated-id",
    "command": "pushall"
  }
}
```

`pushall` 只应用于：

- 服务启动后获取初始快照。
- MQTT 断线重连后重新同步状态。
- 长时间没有收到 `push_status` 时兜底。
- 用户手动刷新。

不要高频轮询 `pushall`。已验证的行为是：订阅 `report` 后，打印机会主动推送 `push_status`，通常约每秒一次，并包含打印状态和 AMS 数据。

## 局域网发现

发现功能只能用于辅助用户配置，不应绕过用户确认自动绑定设备。推荐发现顺序：

1. 扫描当前网段的 Bambu 常见端口。
2. 使用 SSDP 查询确认设备身份。
3. 把候选设备展示给用户确认。
4. 用户录入或确认 `serial` 和 `access_code` 后保存配置。

### TCP 端口特征

| 端口 | 用途 | 识别价值 |
|---|---|---|
| `8883/tcp` | MQTT over TLS | 强特征 |
| `990/tcp` | FTPS | 强特征 |

同一设备同时开放 `8883` 和 `990` 时，高度疑似 Bambu 打印机。端口扫描只能作为候选发现，不能替代 SSDP 或用户确认。

### SSDP 特征

Bambu 设备可响应 SSDP 查询，推荐查询目标：

```text
ST: urn:bambulab-com:device:3dprinter:1
```

典型响应字段：

| 字段 | 含义 |
|---|---|
| `ST` | 设备类型，期望为 `urn:bambulab-com:device:3dprinter:1` |
| `USN` | 打印机序列号，通常可作为 MQTT topic 中的 `<serial>` |
| `DevModel.bambu.com` | 设备型号代码 |
| `DevName.bambu.com` | 打印机显示名称 |
| `DevConnect.bambu.com` | 当前连接模式，例如 cloud / local 相关状态 |
| `DevBind.bambu.com` | 绑定状态 |
| `Devseclink.bambu.com` | 安全连接状态 |
| `DevInf.bambu.com` | 网络接口 |
| `DevVersion.bambu.com` | 固件版本 |

## MQTT 报文结构

典型消息：

```json
{
  "print": {
    "command": "push_status",
    "gcode_state": "RUNNING",
    "mc_percent": 0,
    "mc_remaining_time": 7,
    "ams": {}
  }
}
```

解析入口：

```text
payload.print
```

`payload.print.command` 用于区分消息类型。`push_status` 是状态快照；其他命令消息通常是控制命令或 G-code 回执。

## 已确认 command

| command | 含义 | 后端处理 |
|---|---|---|
| `push_status` | 打印机状态快照 | 核心状态来源 |
| `project_file` | 打印任务文件下发/任务发起回执 | 记录任务请求 |
| `gcode_line` | G-code 命令或执行回执 | 记录原始事件，通常不驱动主状态 |
| `pause` | 暂停命令回执 | 命令事件；最终状态看 `gcode_state` |
| `resume` | 继续命令回执 | 命令事件；最终状态看 `gcode_state` |
| `stop` | 停止/终止命令回执 | 命令事件；后续 `FAILED` 可结合此事件判断为用户取消 |
| `clean_print_error` | 清理错误命令回执 | 记录错误处理事件 |
| `ams_select_slot` | AMS 槽位选择回执 | 记录选择意图；最终槽位状态看后续 `push_status` |
| `ams_change_filament` | AMS 换料/卸料回执 | 记录换料命令；实际耗材变化看槽位快照 |
| `ams_get_rfid` | 触发 AMS 读取 RFID 回执 | 记录重读动作；后续 `push_status` 会更新槽位字段 |
| `ams_filament_setting` | 手动设置 AMS 槽位耗材 | 第三方/手动耗材入口之一 |
| `extrusion_cali_get` | 获取挤出校准信息 | 记录原始回执；失败不等于耗材设置失败 |
| `extrusion_cali_sel` | 选择挤出校准 | 记录原始回执 |
| `ams_filament_drying` | AMS 干燥启停回执 | 记录干燥参数；状态看 AMS 单元字段 |
| `set_fan` | 风扇速度设置回执 | 记录诊断/环境事件，不驱动库存核心逻辑 |
| `set_airduct` | 风道/仓温模式设置回执 | 记录诊断/环境事件，具体模式按机型确认 |

命令回执字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `sequence_id` | string | 命令序列号，用于去重和关联 |
| `result` | string | 常见 `SUCCESS` / `FAIL` |
| `reason` | string | 常见 `SUCCESS` / `ERROR STATE` |
| `err_code` | int | 命令错误码；不能单独作为成功失败依据 |
| `param` | string | 命令参数，`gcode_line` 中可能是 G-code |
| `return_code` | string | G-code 回执编号 |
| `source` | int | G-code 来源编码，语义待继续确认 |
| `ams_id` | int/string | AMS 单元 ID，常见于 AMS 相关命令 |
| `slot_id` | int | AMS 槽位 ID；`255` 可出现在卸料/无目标场景 |
| `target` | int | AMS 换料目标槽位，语义需结合命令 |
| `tray_id` | int | 手动设置耗材时的槽位 ID |
| `tray_type` | string | 手动设置耗材类型 |
| `tray_info_idx` | string | 手动设置耗材 preset / 产品代码 |
| `tray_color` | string | 手动设置耗材颜色 |
| `fan_index` | int | 风扇索引 |
| `speed` | int | 风扇目标速度，常见 `0`-`100` |
| `modeId` | int | 风道/仓温模式 ID，已观察 `0` / `1` |
| `mode` | int | 干燥模式，已观察 `1` 启动、`0` 停止 |
| `temp` | int | 干燥目标温度 |
| `cooling_temp` | int | 干燥冷却温度 |
| `duration` | int | 干燥时长，已观察单位为小时 |
| `filament` | string | 干燥材料类型 |
| `rotate_tray` | bool | 干燥时是否转动料盘 |

## 打印状态字段

### 主状态

| 字段 | 类型 | 已观察值 | 含义 |
|---|---|---|---|
| `gcode_state` | string | `FINISH`、`RUNNING`、`PAUSE`、`FAILED` | 打印任务主状态 |
| `print_type` | string | `cloud`、`local` | 任务来源 |
| `mc_percent` | int | `0`-`100` | 打印进度百分比 |
| `mc_remaining_time` | int | 整数 | 剩余时间；实测语义接近分钟 |
| `gcode_file` | string | 路径字符串 | 当前 G-code 文件 |
| `subtask_name` | string | 任意字符串 | 任务/盘名称 |
| `project_id` | string | 任意字符串 | 项目 ID |
| `profile_id` | string | 任意字符串 | 配置 ID |
| `task_id` | string | 任意字符串 | 任务 ID，建议作为任务关联候选 |

状态机建议：

```text
unknown/FINISH/FAILED -> RUNNING = print.started
RUNNING -> PAUSE = print.paused
PAUSE -> RUNNING = print.resumed
RUNNING/PAUSE -> FINISH = print.finished
RUNNING/PAUSE -> FAILED = print.failed 或 print.cancelled
```

判断原则：

- `gcode_state` 是主状态。
- `pause` / `resume` / `stop` 只是命令回执，不代表最终状态已经切换。
- 如果最近收到 `stop SUCCESS`，随后 `gcode_state=FAILED`，业务上应优先标记为用户取消，而不是设备故障。
- 状态事件必须基于上一帧和当前帧比较去重，避免每秒重复生成业务事件。

### 阶段和动作字段

这些字段已出现但语义尚未完全确认，应保留原始值，谨慎用于核心业务判断。

| 字段 | 已观察值 | 说明 |
|---|---|---|
| `mc_print_stage` | `"1"`、`"2"`、`"3"` | 阶段字符串；实测 `"2"` 运行/准备，`"3"` 暂停，`"1"` 完成/失败/空闲 |
| `mc_stage` | `1`、`2`、`3`、`1281` | 阶段数字；`1281` 曾出现在停止后的失败状态 |
| `mc_action` | `255`、`13`、`269`、`525`、`541`、`1028`、`1279` | 动作码，待映射 |
| `print_real_action` | `0`、`1`、`2`、`4` | 真实动作码，待映射 |
| `print_gcode_action` | `255`、`13`、`29`、`4` | G-code 动作码，待映射 |
| `stg_cur` | `-1`、`13`、`4`、`29` | 当前准备阶段/动作，待映射 |
| `stg` | list[int] | 阶段列表 |

### 错误字段

| 字段 | 类型 | 含义 |
|---|---|---|
| `print_error` | int | 打印错误码 |
| `mc_print_error_code` | string | 打印机错误码字符串 |
| `mc_err` | int | 打印机错误码数字 |
| `fail_reason` | string | 失败原因 |

建议错误分类：

```text
if recent_stop_success and gcode_state == FAILED:
    terminal_reason = user_cancelled
elif gcode_state == FAILED:
    terminal_reason = failed
else:
    terminal_reason = none
```

## 温度和风扇字段

| 字段 | 类型 | 含义 |
|---|---|---|
| `nozzle_temper` | float | 喷嘴当前温度 |
| `nozzle_target_temper` | float | 喷嘴目标温度 |
| `bed_temper` | float | 热床当前温度 |
| `bed_target_temper` | float | 热床目标温度 |
| `chamber_temper` | float/string | 腔体温度，机型相关 |
| `cooling_fan_speed` | string | 冷却风扇速度 |
| `big_fan1_speed` | string | 大风扇 1 速度，物理映射待机型确认 |
| `big_fan2_speed` | string | 大风扇 2 速度，物理映射待机型确认 |
| `chamber_fan_speed` | string | 腔体风扇速度，机型相关 |
| `heatbreak_fan_speed` | string | 热端/喉管风扇速度 |
| `fan_gear` | int | 风扇组合状态或编码值，待映射 |
| `aux_part_fan` | bool | 辅助风扇布尔状态，机型相关 |

库存系统核心逻辑不应依赖风扇字段；这些字段可用于运行诊断或环境记录。

已观察 `set_fan` 命令使用 `fan_index` 和 `speed` 控制风扇。`speed` 是用户侧百分比，后续 `push_status` 中的速度字段通常是内部档位字符串，不一定等于百分比。

| `fan_index` | 已观察关联字段 | 后端建议 |
|---|---|---|
| `1` | `cooling_fan_speed` | 可记录为候选工具头/部件冷却风扇；物理名称按机型校准 |
| `2` | `big_fan1_speed` | 可记录为候选大风扇 1；物理名称按机型校准 |
| `3` | `big_fan2_speed` | 可记录为候选大风扇 2；物理名称按机型校准 |
| `10` | 暂未稳定映射到上述状态字段 | 保留原始命令，不要强行映射 |

`set_airduct.modeId` 已观察 `0` 和 `1`。它和仓温保持、风道模式的 UI 含义需要按机型建立映射；后端应先记录原始值。

## AMS 数据结构

AMS 数据位于：

```text
payload.print.ams
```

根结构示例：

```json
{
  "ams": [],
  "ams_exist_bits": "11",
  "tray_exist_bits": "1000f",
  "tray_is_bbl_bits": "1000f",
  "tray_now": "255",
  "tray_pre": "255",
  "tray_tar": "255"
}
```

根字段：

| 字段 | 类型 | 含义 |
|---|---|---|
| `ams` | list | AMS 单元列表 |
| `ams_exist_bits` | string | 已连接 AMS 位图 |
| `ams_exist_bits_raw` | string | 原始 AMS 位图 |
| `tray_exist_bits` | string | 槽位存在位图 |
| `tray_is_bbl_bits` | string | Bambu 官方 RFID 槽位位图 |
| `tray_read_done_bits` | string | RFID 读取完成位图 |
| `tray_reading_bits` | string | 正在读取 RFID 位图 |
| `tray_hall_out_bits` | string | 霍尔/出料相关状态，待确认 |
| `tray_now` | string | 当前槽位；`255` 常表示无当前槽位/未选中 |
| `tray_pre` | string | 上一个槽位 |
| `tray_tar` | string | 目标槽位 |
| `cali_id` | int | 校准相关 |
| `cali_stat` | int | 校准状态 |
| `insert_flag` | bool | 插入/连接标志，待确认 |
| `power_on_flag` | bool | 上电标志 |
| `unbind_ams_stat` | int | 解绑状态 |
| `version` | int | AMS 数据结构或固件版本 |

## AMS 单元字段

字段路径：

```text
payload.print.ams.ams[]
```

| 字段 | 类型 | 含义 |
|---|---|---|
| `id` | string | AMS 单元 ID |
| `info` | string | AMS 型号/类型代码，需按机型建立映射 |
| `temp` | string | AMS 内温度，摄氏度字符串 |
| `humidity` | string | 湿度等级/档位 |
| `humidity_raw` | string | 原始湿度值 |
| `dry_time` | int | 干燥剩余/当前时间，语义待确认 |
| `dry_setting.dry_duration` | int | 干燥时长，未启用时可能为 `-1` |
| `dry_setting.dry_temperature` | int | 干燥温度，未启用时可能为 `-1` |
| `dry_setting.dry_filament` | string | 干燥耗材类型 |
| `dry_sf_reason` | list | 干燥相关原因/状态 |
| `tray` | list | 槽位列表 |

### AMS 干燥状态

干燥启停会先出现 `ams_filament_drying` 回执，再由后续 `push_status` 更新 AMS 单元字段。

已确认字段：

| 字段 | 已观察值/含义 |
|---|---|
| `ams_filament_drying.ams_id` | 目标 AMS 单元 |
| `mode` | `1` 启动干燥，`0` 停止干燥 |
| `filament` | 干燥材料类型，如 `PLA` / `PETG`；停止时可为空 |
| `temp` | 干燥目标温度 |
| `cooling_temp` | 冷却温度 |
| `duration` | 干燥时长，已观察单位为小时 |
| `dry_setting.dry_duration` | 启动后同步为干燥时长；未启用为 `-1` |
| `dry_setting.dry_temperature` | 启动后同步为干燥温度；未启用为 `-1` |
| `dry_setting.dry_filament` | 启动后同步为材料类型；未启用为空 |
| `dry_time` | 启动后可出现 `720` 这类分钟数；停止后可能有短暂残留帧 |
| `dry_sf_reason` | 已观察 `[]`、`[2]`、`[3]`、`[4]`、`[6]`、`[9]`，具体枚举仍需谨慎映射 |

实现建议：

- 干燥状态以 AMS 单元的 `dry_setting` 和 `dry_time` 为准，命令回执只作为事件来源。
- 停止干燥后要等待后续若干帧确认 `dry_setting` 回到未启用状态，避免被短暂残留的 `dry_time` 误导。
- 库存系统可把干燥历史作为耗材维护记录，但不要把它和耗材用量扣减耦合。

## AMS 槽位字段

字段路径：

```text
payload.print.ams.ams[].tray[]
```

示例：

```json
{
  "id": "1",
  "tray_type": "PLA",
  "tray_sub_brands": "PLA Basic",
  "tray_color": "000000FF",
  "remain": 92,
  "tag_uid": "RFID_TAG_UID",
  "tray_uuid": "BAMBU_TRAY_UUID",
  "tray_weight": "1000",
  "tray_info_idx": "GFA00",
  "tray_id_name": "A00-K00"
}
```

字段字典：

| 字段 | 类型 | 含义 | 后端建议 |
|---|---|---|---|
| `id` | string | AMS 内槽位编号 | 与 `ams.id` 组成当前位置 |
| `tray_uuid` | string | Bambu 官方料卷/料盘 UUID | 优先作为耗材唯一识别 |
| `tag_uid` | string | RFID 标签芯片 UID | `tray_uuid` 无效时兜底 |
| `tray_type` | string | 材料类型，如 PLA/PETG | 库存属性 |
| `tray_sub_brands` | string | Bambu 子品牌/系列 | 库存属性 |
| `tray_color` | string | 颜色，格式接近 `RRGGBBAA` | 库存属性 |
| `cols` | list[string] | 多色/颜色列表 | 多色料支持 |
| `remain` | int | 剩余百分比 | 官方 RFID 余量参考 |
| `tray_weight` | string | 标称重量或料卷重量字段 | 不要直接当实时剩余克重 |
| `total_len` | int | 长度字段，单位疑似 mm | 保留，待验证 |
| `tray_info_idx` | string | Bambu 材料 preset / 产品代码 | 可用于材料映射 |
| `tray_id_name` | string | 颜色/SKU 代码 | 可用于 SKU 映射 |
| `tray_diameter` | string | 线径 |
| `nozzle_temp_min` | string | 推荐喷嘴最低温 |
| `nozzle_temp_max` | string | 推荐喷嘴最高温 |
| `bed_temp` | string | 推荐热床温度字段 |
| `bed_temp_type` | string | 热床温度类型，待确认 |
| `drying_temp` | string | 推荐干燥温度 |
| `drying_time` | string | 推荐干燥时间 |
| `state` | int | 槽位状态，已观察稳定可识别为 `11`，读取/过渡常见 `27` |
| `ctype` | int | 颜色/耗材类型编码，待确认 |
| `cali_idx` | int | 校准索引 |
| `xcam_info` | string | 视觉/相机相关信息，待确认 |

### 槽位状态和手动耗材

槽位在取出、插入、换槽、RFID 重读和手动设置期间会经历多种过渡状态。已观察 `state` 包括：

```text
0, 1, 4, 5, 9, 10, 11, 17, 21, 25, 27
```

目前只建议做保守解释：

| `state` | 建议解释 |
|---|---|
| `11` | 稳定槽位状态，可用于确认当前位置和耗材身份 |
| `27` | 已读到耗材字段但仍处于读取/过渡状态；`remain` 可能还是 `-1` |
| 其他值 | 取出、插入、装载、退料或 RFID 读取过程中的过渡状态，先保留原始值 |

第三方或手动设置耗材时，槽位可能出现：

```json
{
  "tray_uuid": "00000000000000000000000000000000",
  "tag_uid": "0000000000000000",
  "tray_type": "PLA",
  "tray_sub_brands": "",
  "tray_color": "RRGGBBAA",
  "tray_info_idx": "GFL99",
  "remain": -1,
  "tray_weight": "0"
}
```

这类耗材没有可自动信任的物理唯一 ID，应进入手动绑定流程。`tray_info_idx`、`tray_type` 和 `tray_color` 只能作为属性，不应作为唯一身份。

## 耗材唯一识别策略

规则：

1. 优先使用 `tray_uuid` 作为耗材主身份。
2. 仅当 `tray_uuid` 缺失、为空、全 0 或明显无效时，才用 `tag_uid` 顶替。
3. 使用 `tag_uid` 顶替时必须生成异常警告，提示用户可能存在误合并或重复建档风险。
4. 两者都无效时进入手动绑定流程。

实测同一官方料卷在不同槽位/不同读卡过程中可以保持相同 `tray_uuid`，但 `tag_uid` 可能发生变化。因此 `tag_uid` 只能作为异常兜底，不能和 `tray_uuid` 平级参与主键判断。

建议实现：

```python
INVALID_TRAY_UUIDS = {
    None,
    "",
    "00000000000000000000000000000000",
}

INVALID_TAG_UIDS = {
    None,
    "",
    "0000000000000000",
}

def resolve_spool_identity(tray):
    tray_uuid = tray.get("tray_uuid")
    tag_uid = tray.get("tag_uid")

    if tray_uuid not in INVALID_TRAY_UUIDS:
        return {
            "identity_key": f"bambu:tray_uuid:{tray_uuid}",
            "identity_source": "tray_uuid",
            "confidence": "high",
            "warning": None,
        }

    if tag_uid not in INVALID_TAG_UIDS:
        return {
            "identity_key": f"bambu:tag_uid:{tag_uid}",
            "identity_source": "tag_uid",
            "confidence": "medium",
            "warning": "该耗材缺少有效 tray_uuid，系统临时使用 tag_uid 识别。请确认是否为同一卷耗材，避免库存重复或误合并。",
        }

    return {
        "identity_key": None,
        "identity_source": "manual_required",
        "confidence": "none",
        "warning": "无法自动识别耗材：tray_uuid 和 tag_uid 均无效。需要手动绑定库存中的料卷。",
    }
```

数据库建议：

```text
spool.id                  系统内部主键
spool.tray_uuid           Bambu 料卷 UUID，可空
spool.tag_uid             RFID 标签 UID，可空
spool.identity_key        bambu:tray_uuid:* / bambu:tag_uid:* / manual:*
spool.identity_source     tray_uuid / tag_uid / manual
spool.identity_confidence high / medium / none
spool.identity_warning    最近一次异常提示
```

如果某卷耗材最初靠 `tag_uid` 建档，后续读到了有效 `tray_uuid`，应支持身份升级：保留原 `tag_uid`，把主身份切换到 `tray_uuid`，并写审计日志。

## 后端事件模型

建议事件：

| 事件 | 触发条件 |
|---|---|
| `printer.connected` | MQTT 连接成功 |
| `printer.disconnected` | MQTT 连接断开 |
| `printer.snapshot` | 收到 `push_status` |
| `print.requested` | 收到 `project_file SUCCESS` |
| `print.started` | `gcode_state` 从非运行态变为 `RUNNING` |
| `print.paused` | `gcode_state` 变为 `PAUSE` |
| `print.resumed` | `gcode_state` 从 `PAUSE` 变为 `RUNNING` |
| `print.finished` | `gcode_state` 变为 `FINISH` |
| `print.cancelled` | 最近有 `stop SUCCESS` 且随后 `gcode_state=FAILED` |
| `print.failed` | 无用户 stop 命令但进入 `FAILED` |
| `ams.slot_seen` | 某槽位读到有效 `tray_uuid` 或 `tag_uid` |
| `ams.slot_changed` | 同一位置的 `tray_uuid` / `tag_uid` 变化 |
| `ams.slot_transition` | 槽位进入取出、插入、读取或退料过渡状态 |
| `spool.moved` | 同一 `identity_key` 出现在不同 AMS 槽位 |
| `spool.remain_changed` | 同一 `identity_key` 的 `remain` 变化 |
| `spool.unidentified` | `tray_uuid` 和 `tag_uid` 均无效 |
| `ams.drying_started` | `ams_filament_drying mode=1` 且后续 AMS 单元进入干燥状态 |
| `ams.drying_stopped` | `ams_filament_drying mode=0` 且后续 AMS 单元退出干燥状态 |
| `printer.fan_changed` | 收到 `set_fan` 或风扇状态字段变化 |
| `printer.airduct_changed` | 收到 `set_airduct` |

核心实体：

```text
Printer
PrintJob
AmsUnit
AmsSlot
Spool
SpoolLocation
RawMqttMessage
PrinterEvent
InventoryEvent
```

## 库存扣减建议

短期可靠策略：

1. 使用 `tray_uuid` / `tag_uid` 识别卷。
2. 使用 `ams.id + tray.id` 记录当前位置。
3. 收到 `print.started` 时记录任务开始快照。
4. 收到 `print.finished` 时按任务用料估算扣减库存。
5. 收到 `print.cancelled` 或 `print.failed` 时按已打印进度或切片阶段估算部分扣减，并标记需要人工确认。
6. 如果 `remain` 发生变化，用它修正官方 RFID 卷的剩余百分比，但不要完全替代用量模型。
7. 只有当槽位状态稳定、身份有效、并且变化经过短时间去抖后，才把槽位变化写入库存位置历史。

`remain` 是官方 RFID/AMS 上报的参考值，不应作为唯一用量来源。实测在 RFID 重读、换槽和重新放回时可能出现 `-1`，也可能在短时间内跳变。系统仍需要结合切片/G-code 用量、任务状态和用户确认机制。

## 待继续验证

- `tray_now`、`tray_pre`、`tray_tar` 在真实换料和长时间挤出时的取值。
- `remain` 在较长打印完成后的刷新时机和粒度。
- `fan_index=10`、`big_fan1_speed`、`big_fan2_speed`、`fan_gear` 与不同机型物理风扇的完整映射。
- `set_airduct.modeId` 与 UI 上仓温保持/风道模式的完整映射。
- 更多第三方非 RFID 耗材和手动耗材 preset 的字段差异。
- 干燥完整周期结束、异常中断、断电恢复时 `dry_setting`、`dry_time`、`dry_sf_reason` 的字段变化。
- 用户取消和设备异常失败的错误码差异。

## 实现优先级

第一阶段：

1. 用户显式配置打印机连接信息。
2. MQTT 连接、订阅、自动重连。
3. `pushall` 初始快照。
4. `push_status` 原始落库。
5. 打印状态机。
6. AMS 槽位快照。
7. `tray_uuid` 优先的耗材身份识别。
8. 槽位变化 / 耗材移动 / 无法识别告警。

第二阶段：

1. 用量估算和库存扣减。
2. 失败/取消任务的部分扣减确认。
3. 第三方耗材手动绑定。
4. Spoolman 或其他库存系统集成。
