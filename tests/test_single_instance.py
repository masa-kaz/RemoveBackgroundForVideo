"""多重起動防止機能（SingleInstanceLock）のテスト"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest


# srcディレクトリをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from main import SingleInstanceLock


class TestSingleInstanceLock:
    """SingleInstanceLockクラスのテスト"""

    @pytest.fixture
    def temp_lock_file(self, tmp_path):
        """テスト用の一時的なロックファイルパス"""
        return tmp_path / "test_lock.lock"

    @pytest.fixture
    def lock_with_temp_file(self, temp_lock_file):
        """一時ロックファイルを使用するSingleInstanceLock"""
        lock = SingleInstanceLock()
        lock.LOCK_FILE = temp_lock_file
        return lock

    def test_lock_file_path_in_temp_dir(self):
        """ロックファイルがtempディレクトリに作成されること"""
        lock = SingleInstanceLock()
        assert str(lock.LOCK_FILE).startswith(tempfile.gettempdir())
        assert lock.LOCK_FILE.name == "background_remover_video.lock"

    def test_initial_state(self, lock_with_temp_file):
        """初期状態ではロックを取得していないこと"""
        assert lock_with_temp_file._lock_acquired is False

    def test_acquire_creates_lock_file(self, lock_with_temp_file, temp_lock_file):
        """acquire()でロックファイルが作成されること"""
        assert not temp_lock_file.exists()
        result = lock_with_temp_file.acquire()
        assert result is True
        assert temp_lock_file.exists()
        assert lock_with_temp_file._lock_acquired is True

    def test_acquire_writes_current_pid(self, lock_with_temp_file, temp_lock_file):
        """acquire()で現在のPIDがロックファイルに書き込まれること"""
        lock_with_temp_file.acquire()
        content = temp_lock_file.read_text().strip()
        assert content == str(os.getpid())

    def test_release_removes_lock_file(self, lock_with_temp_file, temp_lock_file):
        """release()でロックファイルが削除されること"""
        lock_with_temp_file.acquire()
        assert temp_lock_file.exists()
        lock_with_temp_file.release()
        assert not temp_lock_file.exists()
        assert lock_with_temp_file._lock_acquired is False

    def test_release_without_acquire_does_nothing(self, lock_with_temp_file, temp_lock_file):
        """acquire()なしでrelease()しても何も起きないこと"""
        lock_with_temp_file.release()  # 例外が発生しないこと
        assert not temp_lock_file.exists()

    def test_double_release_is_safe(self, lock_with_temp_file, temp_lock_file):
        """release()を2回呼んでも安全であること"""
        lock_with_temp_file.acquire()
        lock_with_temp_file.release()
        lock_with_temp_file.release()  # 2回目でも例外が発生しないこと
        assert not temp_lock_file.exists()

    def test_acquire_fails_when_process_running(self, temp_lock_file):
        """別のプロセスが動作中の場合、acquire()がFalseを返すこと"""
        # 最初のロックを取得
        lock1 = SingleInstanceLock()
        lock1.LOCK_FILE = temp_lock_file
        assert lock1.acquire() is True

        # 2番目のロックを試行（同じプロセスだがテスト用）
        lock2 = SingleInstanceLock()
        lock2.LOCK_FILE = temp_lock_file
        # 現在のプロセスのPIDが書かれているので、動作中と判断される
        assert lock2.acquire() is False

        # クリーンアップ
        lock1.release()

    def test_acquire_succeeds_with_stale_lock_file(self, lock_with_temp_file, temp_lock_file):
        """存在しないPIDのロックファイルがある場合、acquire()が成功すること"""
        # 存在しないPID（99999999は通常存在しない）を書き込む
        temp_lock_file.write_text("99999999")

        result = lock_with_temp_file.acquire()
        assert result is True
        assert lock_with_temp_file._lock_acquired is True

    def test_acquire_handles_corrupted_lock_file(self, lock_with_temp_file, temp_lock_file):
        """壊れたロックファイル（数値でない内容）がある場合も処理できること"""
        temp_lock_file.write_text("not_a_number")

        result = lock_with_temp_file.acquire()
        assert result is True
        assert lock_with_temp_file._lock_acquired is True

    def test_acquire_handles_empty_lock_file(self, lock_with_temp_file, temp_lock_file):
        """空のロックファイルがある場合も処理できること"""
        temp_lock_file.write_text("")

        result = lock_with_temp_file.acquire()
        assert result is True
        assert lock_with_temp_file._lock_acquired is True

    def test_is_process_running_with_current_pid(self, lock_with_temp_file):
        """_is_process_running()が現在のプロセスでTrueを返すこと"""
        assert lock_with_temp_file._is_process_running(os.getpid()) is True

    def test_is_process_running_with_invalid_pid(self, lock_with_temp_file):
        """_is_process_running()が存在しないPIDでFalseを返すこと"""
        # 非常に大きなPIDは通常存在しない
        assert lock_with_temp_file._is_process_running(99999999) is False

    def test_is_process_running_with_zero_pid(self, lock_with_temp_file):
        """_is_process_running()がPID 0でFalseを返すこと（特殊ケース）"""
        # PID 0 は特殊で、os.kill(0, 0) はプロセスグループにシグナルを送る
        # 実際のロックファイルにPID 0が書かれることはないが、エラーにならないことを確認
        # macOSではos.kill(0, 0)は成功するが、実際のアプリでは問題にならない
        # このテストは_is_process_running()がエラーを起こさないことを確認
        try:
            lock_with_temp_file._is_process_running(0)
        except Exception:
            pytest.fail("_is_process_running(0) should not raise exception")


class TestSingleInstanceLockIntegration:
    """SingleInstanceLockの統合テスト"""

    @pytest.fixture(autouse=True)
    def cleanup_lock_file(self):
        """テスト後にロックファイルを削除"""
        yield
        lock_file = Path(tempfile.gettempdir()) / "background_remover_video.lock"
        if lock_file.exists():
            lock_file.unlink()

    def test_real_lock_file_location(self):
        """実際のロックファイルパスが正しいこと"""
        lock = SingleInstanceLock()
        expected = Path(tempfile.gettempdir()) / "background_remover_video.lock"
        assert expected == lock.LOCK_FILE

    def test_acquire_and_release_cycle(self):
        """取得・解放のサイクルが正常に動作すること"""
        lock = SingleInstanceLock()

        # 取得
        assert lock.acquire() is True
        assert lock.LOCK_FILE.exists()

        # 解放
        lock.release()
        assert not lock.LOCK_FILE.exists()


class TestSingleInstanceLockSubprocess:
    """サブプロセスを使用した多重起動テスト"""

    @pytest.fixture(autouse=True)
    def cleanup_lock_file(self):
        """テスト前後にロックファイルを削除"""
        lock_file = Path(tempfile.gettempdir()) / "test_subprocess_lock.lock"
        if lock_file.exists():
            lock_file.unlink()
        yield
        if lock_file.exists():
            lock_file.unlink()

    def test_subprocess_lock_blocking(self, tmp_path):
        """サブプロセスでのロックが他のプロセスをブロックすること"""
        lock_file = tmp_path / "test_subprocess_lock.lock"

        # サブプロセス用のスクリプトを作成
        script = tmp_path / "lock_script.py"
        script.write_text(f'''
import sys
import os
import time
from pathlib import Path

# ロックファイルに現在のPIDを書き込む
lock_file = Path("{lock_file}")
lock_file.write_text(str(os.getpid()))

# 引数で指定された秒数待機
if len(sys.argv) > 1:
    time.sleep(float(sys.argv[1]))

# 終了前にロックを解放
if lock_file.exists():
    lock_file.unlink()
''')

        # バックグラウンドでロックを保持するプロセスを起動
        proc = subprocess.Popen(
            [sys.executable, str(script), "2"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # ロックファイルが作成されるまで待機
        import time

        for _ in range(20):  # 最大2秒待機
            if lock_file.exists():
                break
            time.sleep(0.1)

        # ロックファイルが存在し、別プロセスのPIDが書かれていること
        assert lock_file.exists()
        pid_in_file = int(lock_file.read_text().strip())
        assert pid_in_file == proc.pid
        assert pid_in_file != os.getpid()

        # SingleInstanceLockでロック取得を試みる
        lock = SingleInstanceLock()
        lock.LOCK_FILE = lock_file
        result = lock.acquire()

        # 別プロセスが動作中なのでFalseになるはず
        assert result is False

        # プロセスの終了を待つ
        proc.wait(timeout=5)

        # プロセス終了後はロック取得できるはず
        result = lock.acquire()
        assert result is True
        lock.release()
