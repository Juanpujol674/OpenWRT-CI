# 高质量<免费>交流群

[IPQ技术讨论群](https://qm.qq.com/q/v7nMhzB4oU)

# 高质量<付费>中转站

[LiBwrt-Ai](https://api.zipimg.cn/register?aff=FFPS3UMJ8HJD)

# 本地编译器

https://github.com/VIKINGYFY/OWRT-Tools.git

# 自用修改版插件

https://github.com/VIKINGYFY/packages.git

# OpenWRT-CI

## 本仓库的编译范围与组件开关

默认云编译仅运行 **AIROHA、IPQ53XX、IPQ60XX-WIFI-NO、IPQ60XX-WIFI-YES**。
其余平台配置和工作流保留，通过开关恢复。`TEST` 是一个单独的测试机型配置，
不是正常编译的前置条件，不参加自动编译；需要时可从 `WRT-TEST` 手动选择。
`WRT-TEST` 的 `TEST=true` 则表示只生成配置、不编译固件，与平台名 `TEST` 含义不同。

在 GitHub 仓库 **Settings → Secrets and variables → Actions → Variables** 设置：

| 变量 | 未设置时 | 用途 |
| --- | --- | --- |
| `ENABLE_ALL_PLATFORMS` | `false` | 设为 `true` 恢复 ROCKCHIP、X86、IPQ807X、IPQ95XX、MEDIATEK 的编译 |
| `AIROHA_ONU_APP` | `true` | 设为 `false` 关闭 AIROHA 的 ONU 主插件及其后端 |
| `AIROHA_ONU_DEBUG` | `false` | 设为 `true` 增加 `airoha-pon-debug` 诊断工具 |
| `AIROHA_ONU_STATUS` | `false` | 设为 `true` 增加 `luci-app-pon-status` 状态卡片 |

变量值请使用小写 `true` / `false`。关闭全平台开关时，`MTK-ALL` 会跳过；
`WRT-TEST` 的选择列表仍保留历史平台，但选择未启用的平台会跳过任务。
开关默认值已写入工作流，不必先创建变量才能编译。

所有平台，包括手动选择的 `TEST`，统一加载 `Config/COMMON.txt`：

- 安装 Nikki；关闭 OpenClash 和 Momo。
- 安装 [openwrt-honk](https://github.com/kenzok8/openwrt-honk) 的 `honk` 和 `luci-app-honk`。
  `openwrt-honk` 是仓库名，不存在名为 `CONFIG_PACKAGE_openwrt-honk` 的上游包选项。
  本仓库固定源码提交和 `source-40164262544` 归档，并提供上游 SHA256 与 provenance，
  避免默认 `staging` 下载地址失效。Honk 需要支持 BTF 的 Linux 6.12+ 内核；
  不会自动启动代理或配置订阅。
- 补齐华为 5G 通信壳的 ECM / NCM / RNDIS USB 网卡、串口、模式切换、NCM 协议组件。
  壳子的 USB 工作模式需与接口设置匹配：ECM/RNDIS 通常对 USB 网卡建立 DHCP 客户端，
  NCM 设备按实际控制端口和 APN 配置 NCM；不自动改写 WAN 或防火墙。
  仍需设备具备可用的 USB 主机接口、对应 USB 控制器驱动及足够供电，尚未进行实机测试。

AIROHA 从 [OpenWrt_ONU_CONFIG](https://github.com/naoki66/OpenWrt_ONU_CONFIG)
固定提交 `3cb13560459f1d51136dac662baa1f399028b2b4` 引入 ONU 软件包。
`luci-app-onu` 强制依赖 `airoha-ponctl` 和 `airoha-pond`，主插件开启时这两个后端必须一起安装；
诊断工具和状态卡片分别由上述开关控制。关闭主插件可以用于兼容性排查。
ONU 软件包只在 AIROHA 配置下启用，需要源码提供 `kmod-airoha-xpon` 等依赖。

组件策略在 `PRIVATE.txt`、手动 `PACKAGE` 调整之后应用，确保不会被覆盖；
要改变上述统一策略请修改 `Config/COMMON.txt` 或 ONU 变量。
工作流在 `make defconfig` 后核对实际选项，依赖缺失或选项被静默移除时直接报错，
避免发布缺少所需组件的固件。首次验证可手动运行 `WRT-TEST`，选择平台并保留 `TEST=true`。

官方版：

https://github.com/immortalwrt/immortalwrt.git

自用版：

https://github.com/VIKINGYFY/immortalwrt.git

# U-BOOT

高通版-沉心：

https://github.com/chenxin527/uboot-qsdk12.5-build.git

高通版-小猪：

https://github.com/1980490718/u-boot-2016.git

联发科-全新版：

https://github.com/VIKINGYFY/UBOOT-CI/releases

联发科-官方版：

https://drive.wrt.moe/uboot/mediatek

# 固件简要说明

固件每天早上5点自动编译。

固件信息里的时间为编译开始的时间，方便核对上游源码提交时间。

MEDIATEK系列、QUALCOMMAX系列、ROCKCHIP系列、X86系列。

# 目录简要说明

workflows——自定义CI配置

Scripts——自定义脚本

Config——自定义配置

## Star History

<a href="https://www.star-history.com/?repos=vikingyfy%2Fopenwrt-ci&type=date&legend=top-left">
 <picture>
   <source media="(prefers-color-scheme: dark)" srcset="https://api.star-history.com/chart?repos=vikingyfy/openwrt-ci&type=date&theme=dark&legend=top-left" />
   <source media="(prefers-color-scheme: light)" srcset="https://api.star-history.com/chart?repos=vikingyfy/openwrt-ci&type=date&legend=top-left" />
   <img alt="Star History Chart" src="https://api.star-history.com/chart?repos=vikingyfy/openwrt-ci&type=date&legend=top-left" />
 </picture>
</a>
