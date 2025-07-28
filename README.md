# AI Chat Extractor CLI

Mac用CLIツールで、Grok/ChatGPT/Gemini/Claudeの共有リンクから会話を自動抽出し、Obsidian Chat View対応Markdownとして出力します。

## 機能

- 各AIサービスの共有リンクから会話を自動抽出
- Obsidian Chat View形式のMarkdown出力
- 設定ファイルによるカスタマイズ
- 自動アップデート機能
- グローバルコマンドとして利用可能

## 対応サービス

- Grok (X.com)
- ChatGPT (OpenAI)
- Gemini (Google)
- Claude (Anthropic)

## インストール

```bash
git clone https://github.com/Ben-1327/AIChat_Extractor.git
cd AIChat_Extractor
chmod +x scripts/install.sh
./scripts/install.sh
```

### 依存関係
- Python 3.10+
- requests, beautifulsoup4, PyYAML
- cloudscraper (Cloudflare対策用)

## 使用方法

```bash
chat_extract [URL] [OPTIONS]
```

### オプション

- `--output DIR`: 出力フォルダ指定
- `--config PATH`: 設定ファイル指定
- `--service SERVICE`: サービス手動指定
- `--verbose`: 詳細ログ出力
- `--styles STYLE`: スタイルオーバーライド
- `--version`: バージョン表示
- `--update`: 自動アップデート
- `--help`: ヘルプ表示

## 設定ファイル

初回実行時に `~/.config/ai_chat_extractor/config.yaml` が自動作成されます。

## アンインストール

```bash
./scripts/uninstall.sh
```

## ライセンス

MIT License