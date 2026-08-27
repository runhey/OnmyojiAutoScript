---
# engine:
#   id: claude
#   model: deepseek-v4-pro
#   env:
#     ANTHROPIC_BASE_URL: https://api.deepseek.com/anthropic
#     ANTHROPIC_API_KEY : ${{ secrets.DEEPSEEK_API_KEY  }}
engine:
  id: codex
  model: gpt-5.6-luna
  env:
    OPENAI_BASE_URL: https://api.ai-pixel.online
    OPENAI_API_KEY : ${{ secrets.PIXEL_API_KEY }}
---






