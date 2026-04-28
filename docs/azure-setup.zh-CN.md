# Azure Speech 开通简明指南

本项目需要一个 Azure AI Speech 资源。你需要从 Azure 门户拿到两个值：

- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION`

## 操作流程

1. 登录 Azure 门户。
2. 创建或进入 Azure AI Speech 资源。
3. 在资源的“密钥和终结点”页面复制 Key 1 或 Key 2。
4. 复制同一页面显示的区域，例如 `eastasia`。
5. 打开本项目 GUI，在 Azure 页面填入 key 和 region。
6. 在诊断页面运行识别测试。

## 配置文件

也可以手工创建 `.env`：

```bash
cp .env.example .env
```

然后填写：

```bash
AZURE_SPEECH_KEY=replace-with-your-azure-speech-key
AZURE_SPEECH_REGION=eastasia
AZURE_SPEECH_LANGUAGE=zh-CN
```

`.env` 已被 git 忽略，不要把真实密钥写入 `.env.example`、README、issue 或截图。

## 额度说明

GUI 中的额度页是本地估算值，来源于本工具记录的识别时长。它不是 Azure 官方账单
或官方剩余额度。需要精确账单时，请以 Azure 门户为准。
