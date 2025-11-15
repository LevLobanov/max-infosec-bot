import aiohttp
import logging

logger = logging.getLogger(__name__)


class BalanceChecker:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://api.aitunnel.ru/v1"

    async def get_balance(self):
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"{self.base_url}/aitunnel/balance", headers=headers
                ) as response:

                    if response.status == 200:
                        data = await response.json()
                        balance = data.get("balance", 0)
                        logger.info(f"Баланс AI Tunnel: {balance} RUB")
                        return balance
                    elif response.status == 401:
                        logger.error("Неверный API ключ AI Tunnel")
                        return None
                    elif response.status == 429:
                        logger.error("Превышен лимит запросов к API статистики")
                        return None
                    else:
                        logger.error(f"Ошибка получения баланса: {response.status}")
                        return None

        except aiohttp.ClientError as e:
            logger.error(f"Сетевая ошибка при проверке баланса: {e}")
            return None
        except Exception as e:
            logger.error(f"Неожиданная ошибка при проверке баланса: {e}")
            return None


_balance_checker_instance = None


def get_balance_checker():
    return _balance_checker_instance


def init_balance_checker(api_key):
    global _balance_checker_instance
    _balance_checker_instance = BalanceChecker(api_key)
    return _balance_checker_instance
