# Azure Speech Setup Quick Guide

[English](azure-setup.en-US.md) | [简体中文](azure-setup.zh-CN.md)

This project needs one Azure AI Speech resource. You need two values from the
Azure portal:

- `AZURE_SPEECH_KEY`
- `AZURE_SPEECH_REGION`

## Steps

1. Sign in to the Azure portal.
2. Create or open an Azure AI Speech resource.
3. Open the resource's "Keys and Endpoint" page and copy Key 1 or Key 2.
4. Copy the region shown on the same page, for example `eastasia`.
5. Open this project's GUI and enter the key and region on the Azure page.
6. Run a recognition test from the diagnostics page.

## Configuration File

You can also create `.env` manually:

```bash
cp .env.example .env
```

Then fill in:

```bash
AZURE_SPEECH_KEY=replace-with-your-azure-speech-key
AZURE_SPEECH_REGION=eastasia
AZURE_SPEECH_LANGUAGE=zh-CN
```

`.env` is ignored by git. Do not put real credentials into `.env.example`,
README files, issues, logs, or screenshots.

## Quota Notes

The GUI quota page is a local estimate based on the recognition duration
recorded by this tool. It is not the official Azure bill or official remaining
quota. Use the Azure portal for exact billing and quota information.
