from flask import Flask, request, jsonify
from datetime import datetime, date

app = Flask(name)
# Эмуляция базы данных
db = {
    # Рабочий, положена дотация, 10000р лимит
    "123456": {
        "fio": "Иванов И.И.",
        "status": "Рабочий",
        "photo_url": "/static/ivanov.jpg",
        "monthly_limit": 10000,
        "spent_from_limit": 50,
        "daily_allowance_date": (date.today() - timedelta(days=1)).isoformat(), # Вчера - дотация доступна
        "spent_today": 0,
        "is_working_day": True # Рабочий день сотрудника и предприятия
    },
    # ИТР, дотация не положена
    "789012": {
        "fio": "Петров П.П.",
        "status": "ИТР",
        "photo_url": "/static/petrov.jpg",
        "monthly_limit": 5000,
        "spent_from_limit": 0,
        "daily_allowance_date": None,
        "spent_today": 0,
        "is_working_day": True
    },
    # Рабочий, уже потратил дотацию
    "345678": {
        "fio": "Сидоров С.С.",
        "status": "Рабочий",
        "photo_url": "/static/sidorov.jpg",
        "monthly_limit": 10000,
        "spent_from_limit": 0,
        "daily_allowance_date": date.today().isoformat(),
        "spent_today": 100,
        "is_working_day": True
    }
}

# --- 1. Эндпоинт для проверки пропуска (п. 6) ---
@app.route('/api/check_employee', methods=['POST'])
def check_employee():
    barcode = request.json.get('barcode')
    employee = db.get(barcode)

    if not employee:
        return jsonify({"success": False, "error": "Пропуск не найден"}), 404

    # Проверка доступной дотации
    today = date.today().isoformat()
    is_allowance_available = (
        employee["status"] == "Рабочий" and
        employee["is_working_day"] and
        employee.get("daily_allowance_date") != today
    )

    available_allowance = 100 - employee["spent_today"] if employee.get("daily_allowance_date") == today else 100 if is_allowance_available else 0
    available_allowance = max(0, available_allowance)

    # Доступный лимит ЗП
    available_limit_zp = employee["monthly_limit"] - employee["spent_from_limit"]

    return jsonify({
        "success": True,
        "fio": employee["fio"],
        "photo_url": employee["photo_url"],
        "status": employee["status"],
        "available_allowance": available_allowance,
        "available_limit_zp": available_limit_zp,
        "total_available": available_allowance + available_limit_zp
    })

# --- 2. Эндпоинт для транзакции (п. 7) ---
@app.route('/api/pay', methods=['POST'])
def process_payment():
    data = request.json
    barcode = data.get('barcode')
    amount = float(data.get('amount', 0))
    location = data.get('location')

    employee = db.get(barcode)

    # 1. Проверка 500р-лимита (п. 5)
    if amount > 500:
        return jsonify({"success": False, "error": "ОШИБКА: Сумма превышает 500 рублей."})

    # Получение данных о доступных средствах (как в check_employee, но для расчетов)
    today = date.today().isoformat()
    is_allowance_available_for_calc = (
        employee["status"] == "Рабочий" and
        employee["is_working_day"] and
        employee.get("daily_allowance_date") != today
    )

    allowance_balance = 100 if is_allowance_available_for_calc else 0
    allowance_balance = max(0, allowance_balance - employee["spent_today"])

    limit_zp_balance = employee["monthly_limit"] - employee["spent_from_limit"]

    # 2. Расчет списаний
    allowance_used = min(amount, allowance_balance)
    remaining_amount = amount - allowance_used
    limit_zp_used = remaining_amount

    # 3. Проверка лимита ЗП (п. 4)
    if limit_zp_used > limit_zp_balance:
        return jsonify({"success": False, "error": "ОТКАЗ: Недостаточно средств на лимите ЗП."})

    # 4. Проведение оплаты и обновление БД
    
    # Обновляем дотацию
    if allowance_used > 0:
        employee["daily_allowance_date"] = today
        employee["spent_today"] += allowance_used
    
    # Обновляем лимит ЗП
    if limit_zp_used > 0:
        employee["spent_from_limit"] += limit_zp_used