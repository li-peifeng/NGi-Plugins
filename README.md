# NGi 源插件

在 MDC-NGi 的 **数据源管理 → 管理源插件 → GitHub 插件仓库** 按名称或 ID 搜索，点击下载并核对版本后安装。正常重启后端后即可在数据源管理中使用。也可以从 [plugins](plugins/) 下载单个 JSON 或 JS 文件，通过本地导入安装。

## 发布插件

1. 准备一个 UTF-8 的 `<id>.json` 或 `<id>.js`，最大 256 KiB，使用插件接口 `api_version: 1`。JS 文件以 `/* NGi-provider` 元数据注释开头。新来源的 ID 以 `plugin_` 开头，使用小写字母、数字和下划线，总长度 8～64 位。
2. 使用三段数字版本号，例如 `1.0.0`。更新同一插件时保留 ID 并提高版本号。
3. 把单个插件文件压缩为 ZIP（可套一层文件夹，ZIP 不超过 512 KiB），上传到主分支的 [install](install/) 目录。ZIP 中的 macOS 与 Windows 压缩附带元数据会自动跳过。
4. [GitHub Actions](https://github.com/li-peifeng/NGi-Plugins/actions) 将插件文件放入 `plugins/<id>/<version>/`，更新 [catalog.json](catalog.json)，并从 `install/` 移除已部署的 ZIP。安装器下载时核对清单中的 SHA-256，再按当前 NGi 的接口校验插件。

清单为每个 ID 展示最高版本，旧版本仍可从相应目录下载。已发布版本的内容固定，内容有变时请使用新版本。部署失败的 ZIP 保留在 `install/`，可在 Actions 日志中查看原因，替换 ZIP 后重新触发。GitHub Actions 解压和读取元数据，插件规则由 NGi 在安装预览时验证。
