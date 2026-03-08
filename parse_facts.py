import re

def parse_facts(filename="facts.txt", output_file="bot/utils/constants.py"):
    try:
        with open(filename, "r", encoding="utf-8") as f:
            text = f.read()
    except FileNotFoundError:
        print(f"❌ Файл {filename} не найден! Создайте его и вставьте сырой текст фактов.")
        return

    uz_facts = []
    ru_facts = []
    
    # Разбиваем текст по нумерации
    items = re.split(r'\n?\d+\.\s+', text)
    
    for item in items:
        if not item.strip():
            continue
            
        # Чистим от "⏳ Илтимос..." и забираем UZ текст
        uz_match = re.search(r'💡 Маслаҳат:\s*(.*?)\s*(?:⏳|💡 Совет:|$)', item, re.DOTALL)
        if uz_match:
            uz_facts.append(uz_match.group(1).strip())
            
        # Чистим от "⏳ Пожалуйста..." и забираем RU текст
        ru_match = re.search(r'💡 Совет:\s*(.*)', item, re.DOTALL)
        if ru_match:
            ru_facts.append(ru_match.group(1).strip())

    # Генерируем код для constants.py
    python_code = "TRADING_FACTS = {\n"
    
    # UZ
    python_code += '    "uz": [\n'
    for uf in uz_facts:
        python_code += f'        "💡 Маслаҳат: {uf.replace(chr(34), chr(92)+chr(34))}",\n'
    python_code += '    ],\n'
    
    # RU
    python_code += '    "ru": [\n'
    for rf in ru_facts:
        python_code += f'        "💡 Совет: {rf.replace(chr(34), chr(92)+chr(34))}",\n'
    python_code += '    ]\n}\n'

    with open(output_file, "w", encoding="utf-8") as out_f:
        out_f.write(python_code)
        
    print(f"✅ Успешно распарсено: {len(uz_facts)} UZ фактов и {len(ru_facts)} RU фактов! Файл сохранен в {output_file}")

if __name__ == "__main__":
    parse_facts()
