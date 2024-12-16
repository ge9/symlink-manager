import os
import shutil
from configparser import ConfigParser

HOME = os.path.expanduser("~")  # ユーザーのホームディレクトリ

def read_config(config_path):
    """設定ファイルを読み込む。"""
    config = ConfigParser(allow_no_value=True)
    config.optionxform = str  # キーの大文字小文字を区別する
    config.read(config_path)
    return config

def normalize_path(path):
    """特殊識別子をホームディレクトリに置き換え、保存先名を変換する。"""
    path = path.replace("HOME", HOME)
    return path.replace("-", "--").replace("/", "-")

def is_same_device(path1, path2):
    """2つのパスが同じデバイス上にあるか確認する。"""
    dev1 = os.stat(path1).st_dev
    dev2 = os.stat(path2).st_dev
    return dev1 == dev2

def confirm_move(src, dst):
    """異なるデバイスの場合、移動確認を行う。"""
    if not is_same_device(src, os.path.dirname(dst)):
        print(f"{src} -> {dst} は異なるデバイスです。移動しますか？ (Y/N)")
        response = input().strip().lower()
        return response == "y"
    return True

def handle_path_conflict(src, is_dir):
    """ファイルとフォルダの競合を処理する。"""
    if os.path.exists(src):
        if is_dir and not os.path.isdir(src):
            print(f"警告: {src} はファイルですが、フォルダが必要です。スキップします。")
            return False
        if not is_dir and not os.path.isfile(src):
            print(f"警告: {src} はフォルダですが、ファイルが必要です。スキップします。")
            return False
    return True

def apply_additions(config):
    """設定に基づいてディレクトリ追加操作を行う。"""
    tasks = []
    for storage_id, base_dir in config["dirs"].items():
        for raw_path, _ in config[storage_id].items():
            if raw_path.startswith("-"):
                continue
            is_dir = raw_path.endswith("/")
            base_path = raw_path.replace("HOME/", "").rstrip("/")
            src = os.path.join(HOME, base_path)
            dst = os.path.join(base_dir, normalize_path(base_path).rstrip("-"))

            if not handle_path_conflict(src, is_dir):
                continue

            tasks.append((src, dst, is_dir))

    # 深い階層から順に処理
    for src, dst, is_dir in sorted(tasks, key=lambda x: len(x[0]), reverse=True):
        if os.path.islink(src):
            if os.readlink(src) == dst:
                print(f"INFO: {src} is already configured correctly. skipping.")
                continue
            else:
                print(f"ERROR: {src} is a wrong symlink. skipping.")
                # os.remove(src)
        elif os.path.exists(src):
            if os.path.exists(dst):
                print(f"ERROR: {dst} already exists. skipping {src}.")
            if not confirm_move(src, dst):
                print(f"INFO: {src} の移動をキャンセルしました。")
                continue
            shutil.move(src, dst)
        else:
            if is_dir:
                os.makedirs(dst, exist_ok=True)
            else:
                open(dst, 'a').close()  # 空ファイルを作成

        os.symlink(dst, src)
        print(f"リンク作成: {src} -> {dst}")

def apply_removals(config):
    """設定に基づいてディレクトリ削除操作を行う。"""
    tasks = []
    for storage_id, base_dir in config["dirs"].items():
        for raw_path, _ in config[storage_id].items():
            if not raw_path.startswith("-"):
                continue
            is_dir = raw_path.endswith("/")
            # TODO: support other prefixes
            base_path = raw_path[1:].lstrip().replace("HOME/", "", 1).rstrip("/")
            src = os.path.join(HOME, base_path)
            dst = os.path.join(base_dir, normalize_path(base_path).rstrip("-"))

            if not handle_path_conflict(src, is_dir):
                continue

            tasks.append((src, dst, is_dir))

    # 浅い階層から順に処理
    for src, dst, is_dir in sorted(tasks, key=lambda x: len(x[0])):
        if os.path.islink(src) and os.readlink(src) == dst:
            os.remove(src)
            print(f"リンク削除: {src} -> {dst}")

            if os.path.exists(dst):
                if not confirm_move(dst, src):
                    print(f"スキップ: {dst} から {src} への移動をキャンセルしました。")
                    continue

                os.makedirs(os.path.dirname(src), exist_ok=True)
                shutil.move(dst, src)

            # 保存先フォルダを削除
            if os.path.isdir(dst) and not os.listdir(dst):
                os.rmdir(dst)
                print(f"保存先フォルダ削除: {dst}")
        else:
            print(f"警告: {src} は正しいリンクではありません。")

def apply(config_path):
    """設定ファイルを適用する。"""
    config = read_config(config_path)
    apply_additions(config)
    apply_removals(config)

if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: python symlink_manager.py <config_path>")
        sys.exit(1)

    config_file = sys.argv[1]

    if not os.path.exists(config_file):
        print(f"設定ファイルが見つかりません: {config_file}")
        sys.exit(1)

    apply(config_file)
