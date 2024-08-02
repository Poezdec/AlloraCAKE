import random
import time
import csv
from datetime import datetime
from web3 import Web3
from eth_account import Account
import threading
from telegram import Bot

# Настройки подключения к Ethereum ноде (например, Infura)
INFURA_URL = "https://arbitrum-mainnet.infura.io/v3/f28dc230304b458795022c41cea8a7a4"
EXPLORER_URL = "https://arbiscan.io/tx/"
TELEGRAM_BOT_TOKEN = "???"
TELEGRAM_CHAT_ID = "???"

web3 = Web3(Web3.HTTPProvider(INFURA_URL))
bot = Bot(token=TELEGRAM_BOT_TOKEN)

# Контрактные адреса и ABI функции
contract_address = "0x1cdc19b13729f16c5284a0ace825f83fc9d799f4"
contract_address = Web3.to_checksum_address(contract_address)
contract_abi = [
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "epoch",
                "type": "uint256"
            },
            {
                "internalType": "address",
                "name": "user",
                "type": "address"
            }
        ],
        "name": "claimable",
        "outputs": [
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256[]",
                "name": "epochs",
                "type": "uint256[]"
            }
        ],
        "name": "claim",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "epoch",
                "type": "uint256"
            }
        ],
        "name": "betBear",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "epoch",
                "type": "uint256"
            }
        ],
        "name": "betBull",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    }
]

# Создание экземпляра контракта
contract = web3.eth.contract(address=contract_address, abi=contract_abi)

# Epoch начальное значение
epoch = 6258

# Чтение приватных ключей из файла
with open('wallets.txt', 'r') as file:
    private_keys = [line.strip() for line in file]

# Перемешивание аккаунтов при старте
random.shuffle(private_keys)


def generate_bet_amounts(num_wallets, min_amount=0.0015, max_amount=0.006):
    """Генерация ставок в указанном диапазоне."""
    amounts = [random.uniform(min_amount, max_amount) for _ in range(num_wallets)]
    return amounts


def calculate_total_amount(amounts):
    """Рассчитываем общую сумму ставок."""
    return sum(amounts)


def distribute_total_amount(total_amount, num_wallets, min_amount=0.0015, max_amount=0.006):
    """Распределяем общую сумму ставок по кошелькам."""
    amounts = []
    for _ in range(num_wallets - 1):
        amount = random.uniform(min_amount, max_amount)
        total_amount -= amount
        amounts.append(amount)
    amounts.append(total_amount)  # добавляем остаток в последнюю сумму
    random.shuffle(amounts)  # перемешиваем суммы
    return amounts


def send_transaction(wallet, function, amount, epoch):
    """Отправка транзакции в смарт-контракт."""
    account = Account.from_key(wallet)
    nonce = web3.eth.get_transaction_count(account.address)

    # Формирование данных транзакции
    txn = function.build_transaction({
        'from': account.address,
        'value': web3.to_wei(amount, 'ether'),
        'gas': 200000,
        'gasPrice': web3.to_wei('2', 'gwei'),
        'nonce': nonce
    })

    signed_txn = web3.eth.account.sign_transaction(txn, private_key=wallet)
    tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    return web3.to_hex(tx_hash)


def check_transaction_status(tx_hash, retries=3, delay=10):
    """Проверка статуса выполнения транзакции с повторными попытками."""
    for attempt in range(retries):
        try:
            receipt = web3.eth.get_transaction_receipt(tx_hash)
            if receipt.status == 1:
                return "Success", f"{EXPLORER_URL}{tx_hash}"
            else:
                return "Fail", f"{EXPLORER_URL}{tx_hash}"
        except Exception as e:
            # Если транзакция не найдена, подождем перед повторной проверкой
            time.sleep(delay)
    # Если все попытки исчерпаны, возвращаем статус ошибки
    return f"Transaction with hash: '{tx_hash}' not found.", f"{EXPLORER_URL}{tx_hash}"


def check_claimable(wallet, epoch):
    """Проверка, можно ли выполнить claim."""
    account = Account.from_key(wallet).address
    epoch_to_check = epoch - 2
    return contract.functions.claimable(epoch_to_check, account).call()


def execute_claim(wallet, epoch):
    """Выполнение claim."""
    account = Account.from_key(wallet)
    nonce = web3.eth.get_transaction_count(account.address)
    epochs = [epoch - 2]

    # Формирование данных транзакции
    txn = contract.functions.claim(epochs).build_transaction({
        'from': account.address,
        'gas': 200000,
        'gasPrice': web3.to_wei('2', 'gwei'),
        'nonce': nonce
    })

    signed_txn = web3.eth.account.sign_transaction(txn, private_key=wallet)
    tx_hash = web3.eth.send_raw_transaction(signed_txn.rawTransaction)
    return web3.to_hex(tx_hash)


def send_telegram_message(message):
    """Отправка сообщения в Telegram."""
    bot.send_message(chat_id=TELEGRAM_CHAT_ID, text=message)


def log_and_record(wallet, action_description, log_file, csv_writer, current_time):
    """Логирование и запись в CSV файл."""
    account = Account.from_key(wallet).address
    log_message = f'{current_time} {account} {action_description}'
    print(log_message)
    csv_writer.writerow([account, action_description, current_time])
    log_file.flush()


def execute_transaction(wallet, function, amount, epoch, delay, log_file, csv_writer):
    """Функция для выполнения транзакции с задержкой."""
    time.sleep(delay)
    current_time = datetime.now().strftime("%H:%M:%S")
    tx_hash = send_transaction(wallet, function, amount, epoch)
    status, link = check_transaction_status(tx_hash)
    if status == "Success":
        action_description = f'выполнил ставку на {function.fn_name} на сумму {amount} ETH, {status} {link}'
    else:
        action_description = f'НЕ выполнил ставку потому что "{status}" {link}'
        log_and_record(wallet, action_description, log_file, csv_writer, current_time)
        if "Bet is too early/late" in status:
            send_telegram_message(f'Software stopped: {action_description}')
            raise SystemExit(f'Software stopped due to error: {action_description}')
    log_and_record(wallet, action_description, log_file, csv_writer, current_time)

    claim_result = check_claimable(wallet, epoch)
    if claim_result:
        claim_delay = random.uniform(5, 30)  # задержка перед выполнением claim
        time.sleep(claim_delay)
        current_time = datetime.now().strftime("%H:%M:%S")
        claim_tx_hash = execute_claim(wallet, epoch)
        claim_status, claim_link = check_transaction_status(claim_tx_hash)
        if claim_status == "Success":
            claim_description = f'claim доступен и ВЫПОЛНЕН {claim_link}'
        else:
            claim_description = f'claim доступен, но НЕ выполнен {claim_link}'
        log_and_record(wallet, claim_description, log_file, csv_writer, current_time)
    else:
        current_time = datetime.now().strftime("%H:%M:%S")
        log_and_record(wallet, "claim НЕ доступен", log_file, csv_writer, current_time)


def run_cycle(epoch, private_keys, log_file, work_file):
    random.shuffle(private_keys)  # Перемешивание перед каждым циклом
    half = len(private_keys) // 2
    wallets_betBear = private_keys[:half]
    wallets_betBull = private_keys[half:]

    betBear_amounts = generate_bet_amounts(len(wallets_betBear))
    total_amount_betBear = calculate_total_amount(betBear_amounts)

    total_amount_betBull = total_amount_betBear * random.uniform(0.97, 1.03)  # учитываем погрешность 3%
    betBull_amounts = distribute_total_amount(total_amount_betBull, len(wallets_betBull))

    # Генерация задержек для транзакций в пределах от 2 до 8 минут (120-480 секунд)
    delays_betBear = [random.uniform(120, 480) for _ in range(len(wallets_betBear))]
    delays_betBull = [random.uniform(120, 480) for _ in range(len(wallets_betBull))]

    threads = []

    # Запись сгенерированных данных в work.csv и логирование
    print("Сгенерированные данные для текущего цикла:")
    work_writer = csv.writer(work_file)
    for wallet, amount, delay in zip(wallets_betBear, betBear_amounts, delays_betBear):
        delay_minutes = int(delay // 60)
        delay_seconds = delay % 60
        address = Account.from_key(wallet).address
        current_time = datetime.now().strftime("%H:%M:%S")
        print(
            f"{current_time} Аккаунт {address} : {delay_minutes} минут {delay_seconds:.2f} секунд : betBear : {amount:.6f}")
        work_writer.writerow(
            [address, f"{delay_minutes} минут {delay_seconds:.2f} секунд", 'betBear', amount, current_time])

    for wallet, amount, delay in zip(wallets_betBull, betBull_amounts, delays_betBull):
        delay_minutes = int(delay // 60)
        delay_seconds = delay % 60
        address = Account.from_key(wallet).address
        current_time = datetime.now().strftime("%H:%M:%S")
        print(
            f"{current_time} Аккаунт {address} : {delay_minutes} минут {delay_seconds:.2f} секунд : betBull : {amount:.6f}")
        work_writer.writerow(
            [address, f"{delay_minutes} минут {delay_seconds:.2f} секунд", 'betBull', amount, current_time])

    work_file.flush()  # Сохранение данных в work.csv

    # Запуск потоков для выполнения транзакций
    for wallet, amount, delay in zip(wallets_betBear, betBear_amounts, delays_betBear):
        t = threading.Thread(target=execute_transaction, args=(
        wallet, contract.functions.betBear(epoch), amount, epoch, delay, log_file, csv.writer(log_file)))
        t.start()
        threads.append(t)

    for wallet, amount, delay in zip(wallets_betBull, betBull_amounts, delays_betBull):
        t = threading.Thread(target=execute_transaction, args=(
        wallet, contract.functions.betBull(epoch), amount, epoch, delay, log_file, csv.writer(log_file)))
        t.start()
        threads.append(t)

    # Ожидание завершения всех потоков
    for t in threads:
        t.join()


def main():
    global epoch

    # Открытие файлов для записи логов
    with open('bet_logs.csv', mode='w', newline='') as log_file, open('work.csv', mode='a', newline='') as work_file:
        csv_writer = csv.writer(log_file)
        csv_writer.writerow(['Account', 'Action', 'Time'])
        work_writer = csv.writer(work_file)
        work_writer.writerow(['Account', 'Delay', 'Bet Type', 'Amount', 'Time'])

        while True:
            cycle_start_time = time.time()
            run_cycle(epoch, private_keys, log_file, work_file)
            epoch += 1
            cycle_end_time = time.time()
            cycle_duration = cycle_end_time - cycle_start_time
            sleep_time = max(0, 600 - cycle_duration)
            time.sleep(sleep_time)


if __name__ == "__main__":
    main()
