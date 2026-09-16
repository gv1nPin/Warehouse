import os
import re

def to_snake_case(name):
    # Преобразует CamelCase в snake_case, разделяет аббревиатуры вроде Dto -> _dto
    name = re.sub(r'(?<!^)(?=[A-Z][a-z])', '_', name)
    name = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name)
    return name.lower()

def rename_contents(root_dir):
    # 1. Сначала переименовываем файлы внутри папок
    for dirpath, dirnames, filenames in os.walk(root_dir, topdown=False):
        for filename in filenames:
            if filename.endswith('.py') and not filename.startswith('__'):
                old_file_path = os.path.join(dirpath, filename)
                
                # Читаем содержимое, чтобы исправить внутренние импорты
                with open(old_file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                
                # Магия: заменяем пути импортов с заглавных на строчные в коде
                # Например: from Warehouse.API.Auth -> from warehouse.api.auth
                modified_content = re.sub(
                    r'(from\s+|import\s+)(Warehouse|Warehouse\.[a-zA-Z.]+)',
                    lambda m: m.group(1) + to_snake_case(m.group(2).replace('.', '/')).replace('/', '.'),
                    content
                )
                
                with open(old_file_path, 'w', encoding='utf-8') as f:
                    f.write(modified_content)
                
                # Переименовываем сам файл
                new_filename = to_snake_case(filename)
                if new_filename != filename:
                    new_file_path = os.path.join(dirpath, new_filename)
                    os.rename(old_file_path, new_file_path)
                    print(f"Файл: {filename} -> {new_filename}")

        # 2. Переименовываем сами папки
        for dirname in dirnames:
            if not dirname.startswith('__') and not dirname.startswith('.'):
                old_dir_path = os.path.join(dirpath, dirname)
                new_dirname = to_snake_case(dirname)
                if new_dirname != dirname:
                    new_dir_path = os.path.join(dirpath, new_dirname)
                    os.rename(old_dir_path, new_dir_path)
                    print(f"Папка: {dirname} -> {new_dirname}")

if __name__ == "__main__":
    target_folder = "Warehouse" # Имя корневой папки
    if os.path.exists(target_folder):
        rename_contents(target_folder)
        # Переименовываем саму корневую папку
        os.rename(target_folder, target_folder.lower())
        print(f"\nГотово! Корень проекта переименован в '{target_folder.lower()}'")
    else:
        print(f"Папка {target_folder} не найдена в текущей директории.")
