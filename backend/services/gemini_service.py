"""OpenRouter text and paired-image inference; never turn API errors into findings."""
import base64
import json
import mimetypes
import os
import time
from pathlib import Path
from openai import OpenAI, APIStatusError
from config import Config

class AIServiceError(RuntimeError):
    def __init__(self, message, retryable=False, code=None):
        super().__init__(message)
        self.retryable = retryable
        self.code = code


def response_text(result):
    """OpenRouter can return an error body even when HTTP status is 200."""
    body = result.model_dump() if hasattr(result, 'model_dump') else result
    error = body.get('error')
    if error:
        code = str(error.get('code', 'unknown')) if isinstance(error, dict) else 'unknown'
        messages = {
            '401': 'The AI provider rejected the configured API key.',
            '402': 'OpenRouter credit is unavailable.',
            '403': 'The AI provider denied this request. Check model access or account limits.',
            '429': 'The AI provider is rate limited. Please retry later.',
            '408': 'The AI provider timed out while processing the images.',
            '500': 'The AI provider encountered a temporary server error.',
            '502': 'The AI model provider returned an invalid response.',
            '503': 'No AI model provider is currently available.',
            '504': 'The AI model provider timed out. Please retry.'}
        raise AIServiceError(messages.get(code, f'AI provider returned an error (code {code}).'),
                             retryable=code in ('408','500','502','503','504'), code=code)
    choices = body.get('choices') or []
    if not choices:
        raise AIServiceError('The AI provider returned no completion. Please retry.', retryable=True)
    choice = choices[0]
    if choice.get('finish_reason') == 'length':
        raise AIServiceError('The AI response exceeded its output limit. Use a model with a smaller reasoning budget or increase the output limit.', code='length')
    content = (choice.get('message') or {}).get('content')
    if not isinstance(content, str) or not content.strip():
        raise AIServiceError('The AI provider returned an empty response. Please retry.', retryable=True)
    if content.strip().lower().startswith(('user safety:', 'assistant safety:', 'safety:')):
        raise AIServiceError('The selected AI model returned a safety label instead of an answer. Please retry.', retryable=True)
    return content.strip()

class GeminiService:
    def __init__(self):
        self.model = os.environ.get('VISION_MODEL', 'openrouter/free')

    def _generate(self, content, model=None):
        keys = Config.get_api_keys()
        if not keys:
            raise AIServiceError('Add a valid OPENROUTER_API_KEY to backend/.env and restart the app.')
        for key in keys:
            reasoning = {'reasoning': {'effort': 'none'}}
            output_limit = 4096
            transient_retried = False
            for attempt in range(3):
                try:
                    with OpenAI(base_url='https://openrouter.ai/api/v1', api_key=key,
                                timeout=90, max_retries=0) as client:
                        result = client.chat.completions.create(
                            model=model or self.model,
                            messages=[{'role': 'user', 'content': content}],
                            max_tokens=output_limit, temperature=0.2,
                            extra_body=reasoning)
                    return response_text(result)
                except APIStatusError as exc:
                    code = exc.status_code
                    if code in (401, 403):
                        break
                    if code == 400 and reasoning and attempt < 2:
                        reasoning = {}
                        output_limit = 16384
                        continue
                    if code in (408, 500, 502, 503, 504) and not transient_retried and attempt < 2:
                        transient_retried = True
                        time.sleep(1)
                        continue
                    messages = {
                        402: 'OpenRouter credit is unavailable. Add credit or select an available free model.',
                        404: 'The configured AI model is unavailable. Update VISION_MODEL/TEXT_MODEL in backend/.env.',
                        429: 'The AI provider is rate limited. Retry later or choose another model.'}
                    raise AIServiceError(messages.get(code, f'AI provider returned HTTP {code}. Please retry.')) from None
                except AIServiceError as exc:
                    if exc.code == '400' and reasoning and attempt < 2:
                        reasoning = {}
                        output_limit = 16384
                        continue
                    if exc.code == 'length' and output_limit < 16384 and attempt < 2:
                        output_limit = 16384
                        continue
                    if exc.retryable and not transient_retried and attempt < 2:
                        transient_retried = True
                        time.sleep(1)
                        continue
                    raise
                except Exception:
                    raise AIServiceError('The AI request failed during transport or response decoding. Please retry.') from None
        raise AIServiceError('OpenRouter rejected the configured keys. Update OPENROUTER_API_KEY in backend/.env and restart.')

    def generate_text(self, prompt):
        return self._generate(prompt, os.environ.get('TEXT_MODEL', 'openrouter/free'))

    def _image(self, value):
        if value.startswith(('https://', 'http://')):
            return value
        path = Path(value)
        mime = mimetypes.guess_type(path.name)[0] or 'image/png'
        return f'data:{mime};base64,' + base64.b64encode(path.read_bytes()).decode()

    def analyze_image(self, image_path_or_url, prompt):
        return self.analyze_images([image_path_or_url], prompt)

    def analyze_images(self, images, prompt):
        content = [{'type': 'text', 'text': prompt}]
        content.extend({'type': 'image_url', 'image_url': {'url': self._image(i)}} for i in images)
        return self._generate(content)

    def check_connection(self):
        self._generate('Reply with exactly OK.')
        return True

def parse_json(text):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[1].rsplit('```', 1)[0].strip()
    try:
        return json.loads(text)
    except (ValueError, TypeError):
        raise AIServiceError('AI returned an invalid structured result. Please retry.') from None

gemini_service = GeminiService()
