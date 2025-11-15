import aiohttp
import json
import logging
from services.balance_checker import get_balance_checker
from config import settings

logger = logging.getLogger(__name__)


class AnalysisResult:
    def __init__(
        self,
        risk_score: int,
        scam_indicators: list,
        analysis: str,
        confidence: float = 0.0,
        cost: float = 0.0,
    ):
        self.risk_score = risk_score
        self.scam_indicators = scam_indicators
        self.analysis = analysis
        self.confidence = confidence
        self.cost = cost


class AITunnelAnalyzer:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.aitunnel.ru/v1"

        self.model = "gpt-4o-mini"
        self.max_tokens = 800
        self.temperature = 0.1

        self.min_balance = 50

    async def check_balance_and_limits(self):
        balance_checker = get_balance_checker()

        if not balance_checker:
            logger.error("Баланс-чекер не инициализирован")
            return False

        balance = await balance_checker.get_balance()

        if balance is None:
            logger.error("Не удалось получить баланс")
            return False

        if balance < self.min_balance:
            logger.error(
                f"Низкий баланс: {balance} RUB (минимум: {self.min_balance} RUB)"
            )
            return False

        logger.info(f"Достаточный баланс: {balance} RUB")
        return True

    async def analyze_message(self, text: str) -> AnalysisResult:
        if not await self.check_balance_and_limits():
            return self._create_balance_error_result()

        system_prompt = self._create_enhanced_system_prompt()

        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": text},
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
            "stream": False,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{self.base_url}/chat/completions",
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=30),
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        return self._parse_success_response(data, text)

                    elif response.status == 402:
                        logger.error("Недостаточно средств на балансе")
                        return self._create_balance_error_result()

                    elif response.status == 429:
                        logger.warning("Превышен лимит запросов")
                        return self._create_rate_limit_result(text)

                    elif response.status == 400:
                        error_data = await response.json()
                        logger.error(f"Ошибка запроса: {error_data}")
                        error_msg = self._parse_provider_error(error_data)
                        return self._create_error_result(text, error_msg)

                    else:
                        logger.error(f"Неизвестная ошибка API: {response.status}")
                        return self._create_error_result(
                            text, f"Ошибка сервиса: {response.status}"
                        )

        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка: {e}")
            return self._create_error_result(text, "Сетевая ошибка")
        except Exception as e:
            logger.error(f"Неожиданная ошибка: {e}")
            return self._create_error_result(text, "Внутренняя ошибка")

    def _parse_provider_error(self, error_data: dict) -> str:
        error_msg = error_data.get("error", {}).get(
            "message", "Неизвестная ошибка провайдера"
        )
        if "model not found" in error_msg.lower():
            return "Модель недоступна"
        elif "invalid api key" in error_msg.lower():
            return "Неверный API ключ"
        else:
            return f"Ошибка AI: {error_msg}"

    def _create_enhanced_system_prompt(self):
        return """Ты эксперт по кибербезопасности и финансовым мошенничествам. Анализируй диалоги на признаки мошеннических схем.

КОНТЕКСТНЫЙ АНАЛИЗ ДИАЛОГА:
- Определи роли собеседников (жертва, мошенник, посредник)
- Проанализируй динамику диалога и смену тем
- Обрати внимание на временные промежутки между сообщениями
- Выяви паттерны давления и манипуляции

КАТЕГОРИИ МОШЕННИЧЕСТВА ДЛЯ АНАЛИЗА:

ФИНАНСОВЫЕ МОШЕННИЧЕСТВА:
• Срочные переводы под предлогом помощи родственникам/друзьям
• Инвестиционные схемы с гарантированной высокой доходностью
• Кредитные аферы (предоплата за оформление, страховки)
• Взломы аккаунтов с просьбой экстренного перевода
• Мошенничества с криптовалютами и NFT

ФИШИНГ И КРАЖА ДАННЫХ:
• Поддельные сайты банков, госуслуг, маркетплейсов
• Запросы паролей, CVV-кодов, SMS-подтверждений
• Поддельные уведомления о блокировках счетов
• "Проверки безопасности" с требованием данных

СОЦИАЛЬНАЯ ИНЖЕНЕРИЯ:
• Выдача за сотрудников банков, правоохранительных органов
• Создание искусственной срочности ("акция заканчивается")
• Манипуляции с эмоциями (помощь "больному ребенку")
• Романтические аферы (создание доверительных отношений)

ТОВАРНЫЕ МОШЕННИЧЕСТВА:
• Продажа несуществующих товаров
• Предоплата без последующей доставки
• Поддельные интернет-магазины
• Обман на площадках объявлений

ТЕХНИЧЕСКИЕ МОШЕННИЧЕСТВА:
• Вредоносные ссылки и файлы
• Поддельные приложения
• СМС-мошенничества
• Мошенничества в мессенджерах

КЛЮЧЕВЫЕ МАРКЕРЫ МОШЕННИЧЕСТВА:
СРОЧНОСТЬ: "Срочно нужно", "Последний шанс", "Акция заканчивается"
КОНФИДЕНЦИАЛЬНОСТЬ: "Никому не говори", "Это секретно"
ОПЛАТА: Нестандартные методы оплаты, предоплата
АНОМАЛИИ: Несоответствующий стиль общения, грамматические ошибки
ДОВЕРИЕ: Выдача за известные организации, создание ложного авторитета

АНАЛИЗИРУЙ СЛЕДУЮЩИЕ АСПЕКТЫ:
1. Инициатива подозрительных тем - кто начинает опасные темы
2. Последовательность действий - есть ли четкий сценарий
3. Эскалация давления - нарастание срочности и требований
4. Противоречия в информации - несоответствия в рассказе
5. Попытки обойти безопасность - просьбы не использовать защитные механизмы

ФОРМАТ ОТВЕТА (ТОЛЬКО JSON):
{
    "risk_score": 0-100,
    "scam_indicators": ["конкретный маркер: описание с цитатой из диалога"],
    "analysis": "Детальный анализ на русском. Укажи конкретные фразы из диалога, которые вызвали подозрения. Проанализируй роли собеседников, динамику диалога и выявленные схемы.",
    "confidence": 0.0-1.0
}

ПРИМЕРЫ КОРРЕКТНЫХ ИНДИКАТОРОВ:
• "Срочный перевод: фраза 'нужно срочно перевести 5000 рублей'"
• "Фишинговая ссылка: предложение перейти по подозрительной ссылке"
• "Социальная инженерия: выдача за сотрудника банка без подтверждения"

Будь объективным и анализируй весь контекст диалога. Учитывай последовательность сообщений и взаимодействие между собеседниками."""

    def _parse_success_response(self, data: dict, original_text: str) -> AnalysisResult:
        try:
            choice = data["choices"][0]
            message_content = choice["message"]["content"]

            result_data = json.loads(message_content)

            usage = data.get("usage", {})
            total_tokens = usage.get("total_tokens", 0)

            logger.info(f"Использовано токенов: {total_tokens}")

            return AnalysisResult(
                risk_score=result_data.get("risk_score", 0),
                scam_indicators=result_data.get("scam_indicators", []),
                analysis=result_data.get("analysis", ""),
                confidence=result_data.get("confidence", 0.5),
                cost=0.0,
            )

        except (KeyError, json.JSONDecodeError, IndexError) as e:
            logger.error(f"Ошибка парсинга ответа AI: {e}")
            logger.error(f"Содержимое ответа: {message_content}")
            return self._create_error_result(original_text, "Ошибка формата ответа AI")

    def _create_balance_error_result(self) -> AnalysisResult:
        return AnalysisResult(
            risk_score=0,
            scam_indicators=["Недостаточно средств на балансе"],
            analysis="Сервис анализа временно недоступен из-за недостатка средств. Попробуйте позже.",
            confidence=0.0,
            cost=0.0,
        )

    def _create_rate_limit_result(self, text: str) -> AnalysisResult:
        return AnalysisResult(
            risk_score=0,
            scam_indicators=["Превышен лимит запросов"],
            analysis="Сервис перегружен. Попробуйте через несколько минут.",
            confidence=0.0,
            cost=0.0,
        )

    def _create_error_result(self, text: str, error_msg: str) -> AnalysisResult:
        return AnalysisResult(
            risk_score=0,
            scam_indicators=["Временные проблемы с анализом"],
            analysis=f"{error_msg}. Используется резервный анализ.",
            confidence=0.0,
            cost=0.0,
        )


ai_analyzer = None


def init_ai_analyzer(api_key):
    global ai_analyzer
    ai_analyzer = AITunnelAnalyzer(api_key)
    return ai_analyzer


async def analyze_message_safe(text: str) -> AnalysisResult:
    if not ai_analyzer:
        api_key = settings.AI_TUNNEL_TOKEN
        if not api_key:
            return AnalysisResult(
                risk_score=0,
                scam_indicators=["API ключ не настроен"],
                analysis="Сервис анализа не настроен. Проверьте конфигурацию AI_TUNNEL_API_KEY.",
                confidence=0.0,
                cost=0.0,
            )
        init_ai_analyzer(api_key)

    if len(text) > 4000:
        text = text[:4000] + "... [текст обрезан]"

    return await ai_analyzer.analyze_message(text) # type: ignore
