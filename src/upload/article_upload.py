import shutil
from pathlib import Path


def upload_article(file, upload_folder, allowed_size):
    # 验证文件格式和大小
    if not file.filename.endswith('.md') or file.content_length > allowed_size:
        return 'Invalid file format or file too large.', 400

    # 使用 pathlib 创建上传文件夹
    upload_path = Path(upload_folder)
    upload_path.mkdir(parents=True, exist_ok=True)

    # 构建文件路径
    file_path = upload_path / file.filename

    # 避免文件名冲突
    if file_path.is_file():
        return 'Upload failed, the file already exists.', 400

    # 保存文件
    file.save(str(file_path))  # 确保转换为字符串
    shutil.copy(str(file_path), str(Path('articles') / file.filename))
    return None
