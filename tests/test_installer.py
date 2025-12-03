"""インストーラースクリプト(.iss)の静的検証テスト

Inno Setupスクリプトの構文・設定を検証する。
実際のインストール動作はWindows実機での手動テストが必要。
"""

import re
from pathlib import Path

import pytest


# インストーラーディレクトリ
INSTALLER_DIR = Path(__file__).parent.parent / "installer"
GPU_ISS_FILE = INSTALLER_DIR / "setup_gpu.iss"
CPU_ISS_FILE = INSTALLER_DIR / "setup_cpu.iss"

# 必須セクション
REQUIRED_SECTIONS = ["Setup", "Languages", "Tasks", "Files", "Icons", "Run", "Code"]

# 必須Setup項目
REQUIRED_SETUP_ITEMS = [
    "AppId",
    "AppName",
    "AppVersion",
    "AppPublisher",
    "DefaultDirName",
    "OutputBaseFilename",
    "Compression",
]


def read_iss_file(file_path: Path) -> str:
    """ISSファイルを読み込む"""
    return file_path.read_text(encoding="utf-8")


def extract_define(content: str, name: str) -> str | None:
    """#define定数を抽出する"""
    pattern = rf'#define\s+{name}\s+"([^"]+)"'
    match = re.search(pattern, content)
    return match.group(1) if match else None


def extract_setup_value(content: str, key: str) -> str | None:
    """[Setup]セクションの値を抽出する"""
    pattern = rf"^\s*{key}\s*=\s*(.+?)$"
    match = re.search(pattern, content, re.MULTILINE)
    return match.group(1).strip() if match else None


def get_sections(content: str) -> list[str]:
    """ISSファイルのセクション名を抽出する"""
    pattern = r"^\[(\w+)\]"
    return re.findall(pattern, content, re.MULTILINE)


class TestIssFilesExist:
    """ISSファイルの存在確認"""

    def test_installer_directory_exists(self):
        """installerディレクトリが存在する"""
        assert INSTALLER_DIR.exists(), f"{INSTALLER_DIR} が存在しません"
        assert INSTALLER_DIR.is_dir(), f"{INSTALLER_DIR} はディレクトリではありません"

    def test_gpu_iss_file_exists(self):
        """GPU版ISSファイルが存在する"""
        assert GPU_ISS_FILE.exists(), f"{GPU_ISS_FILE} が存在しません"

    def test_cpu_iss_file_exists(self):
        """CPU版ISSファイルが存在する"""
        assert CPU_ISS_FILE.exists(), f"{CPU_ISS_FILE} が存在しません"


class TestIssFileEncoding:
    """ISSファイルのエンコーディング確認"""

    def test_gpu_iss_is_utf8(self):
        """GPU版ISSファイルがUTF-8で読める"""
        content = read_iss_file(GPU_ISS_FILE)
        assert len(content) > 0

    def test_cpu_iss_is_utf8(self):
        """CPU版ISSファイルがUTF-8で読める"""
        content = read_iss_file(CPU_ISS_FILE)
        assert len(content) > 0


class TestRequiredSections:
    """必須セクションの存在確認"""

    def test_gpu_iss_has_required_sections(self):
        """GPU版に必須セクションがある"""
        content = read_iss_file(GPU_ISS_FILE)
        sections = get_sections(content)

        for section in REQUIRED_SECTIONS:
            assert section in sections, f"GPU版に [{section}] セクションがありません"

    def test_cpu_iss_has_required_sections(self):
        """CPU版に必須セクションがある"""
        content = read_iss_file(CPU_ISS_FILE)
        sections = get_sections(content)

        for section in REQUIRED_SECTIONS:
            assert section in sections, f"CPU版に [{section}] セクションがありません"


class TestSetupSection:
    """[Setup]セクションの検証"""

    def test_gpu_iss_has_required_setup_items(self):
        """GPU版に必須Setup項目がある"""
        content = read_iss_file(GPU_ISS_FILE)

        for item in REQUIRED_SETUP_ITEMS:
            value = extract_setup_value(content, item)
            assert value is not None, f"GPU版に {item} がありません"

    def test_cpu_iss_has_required_setup_items(self):
        """CPU版に必須Setup項目がある"""
        content = read_iss_file(CPU_ISS_FILE)

        for item in REQUIRED_SETUP_ITEMS:
            value = extract_setup_value(content, item)
            assert value is not None, f"CPU版に {item} がありません"

    def test_gpu_output_filename_contains_gpu(self):
        """GPU版の出力ファイル名にGPUが含まれる"""
        content = read_iss_file(GPU_ISS_FILE)
        output_filename = extract_setup_value(content, "OutputBaseFilename")
        assert output_filename is not None
        assert "GPU" in output_filename, (
            f"GPU版の出力ファイル名にGPUが含まれていません: {output_filename}"
        )

    def test_cpu_output_filename_contains_cpu(self):
        """CPU版の出力ファイル名にCPUが含まれる"""
        content = read_iss_file(CPU_ISS_FILE)
        output_filename = extract_setup_value(content, "OutputBaseFilename")
        assert output_filename is not None
        assert "CPU" in output_filename, (
            f"CPU版の出力ファイル名にCPUが含まれていません: {output_filename}"
        )


class TestVersionConsistency:
    """バージョン番号の整合性"""

    def test_version_format_valid(self):
        """バージョン番号が正しい形式"""
        gpu_content = read_iss_file(GPU_ISS_FILE)
        cpu_content = read_iss_file(CPU_ISS_FILE)

        gpu_version = extract_define(gpu_content, "MyAppVersion")
        cpu_version = extract_define(cpu_content, "MyAppVersion")

        # セマンティックバージョニング形式（x.y.z）
        version_pattern = r"^\d+\.\d+\.\d+$"

        assert gpu_version is not None, "GPU版のバージョンが定義されていません"
        assert cpu_version is not None, "CPU版のバージョンが定義されていません"
        assert re.match(version_pattern, gpu_version), f"GPU版のバージョン形式が不正: {gpu_version}"
        assert re.match(version_pattern, cpu_version), f"CPU版のバージョン形式が不正: {cpu_version}"

    def test_gpu_cpu_version_match(self):
        """GPU版とCPU版のバージョンが一致"""
        gpu_content = read_iss_file(GPU_ISS_FILE)
        cpu_content = read_iss_file(CPU_ISS_FILE)

        gpu_version = extract_define(gpu_content, "MyAppVersion")
        cpu_version = extract_define(cpu_content, "MyAppVersion")

        assert gpu_version == cpu_version, (
            f"バージョンが不一致: GPU={gpu_version}, CPU={cpu_version}"
        )

    def test_app_id_match(self):
        """GPU版とCPU版のAppIdが一致（同じアプリとして認識）"""
        gpu_content = read_iss_file(GPU_ISS_FILE)
        cpu_content = read_iss_file(CPU_ISS_FILE)

        gpu_app_id = extract_setup_value(gpu_content, "AppId")
        cpu_app_id = extract_setup_value(cpu_content, "AppId")

        assert gpu_app_id == cpu_app_id, f"AppIdが不一致: GPU={gpu_app_id}, CPU={cpu_app_id}"


class TestGpuDetectionCode:
    """GPU検出コードの存在確認"""

    def test_gpu_iss_has_nvidia_detection(self):
        """GPU版にNVIDIA検出コードがある"""
        content = read_iss_file(GPU_ISS_FILE)

        assert "nvidia-smi" in content.lower(), "GPU版にnvidia-smi呼び出しがありません"
        assert "DetectNvidiaGPU" in content, "GPU版にDetectNvidiaGPU関数がありません"

    def test_cpu_iss_has_nvidia_detection(self):
        """CPU版にもNVIDIA検出コードがある（警告表示用）"""
        content = read_iss_file(CPU_ISS_FILE)

        assert "nvidia-smi" in content.lower(), "CPU版にnvidia-smi呼び出しがありません"
        assert "DetectNvidiaGPU" in content, "CPU版にDetectNvidiaGPU関数がありません"

    def test_gpu_iss_blocks_without_gpu(self):
        """GPU版はGPU未検出時にインストールをブロックする"""
        content = read_iss_file(GPU_ISS_FILE)

        # GPU未検出時にFalseを返すロジックがあることを確認
        assert "Result := False" in content, "GPU版にインストールブロック処理がありません"
        assert "mbError" in content, "GPU版にエラーメッセージ表示がありません"

    def test_cpu_iss_warns_with_gpu(self):
        """CPU版はGPU検出時に警告を表示する"""
        content = read_iss_file(CPU_ISS_FILE)

        # GPU検出時に警告を表示するロジックがあることを確認
        assert "GPU版" in content, "CPU版にGPU版推奨メッセージがありません"
        assert "mbConfirmation" in content, "CPU版に確認ダイアログがありません"


class TestExeNameSettings:
    """実行ファイル名の設定確認"""

    def test_gpu_exe_name(self):
        """GPU版の実行ファイル名が正しい"""
        content = read_iss_file(GPU_ISS_FILE)
        exe_name = extract_define(content, "MyAppExeName")

        assert exe_name is not None, "GPU版のMyAppExeNameが定義されていません"
        assert "GPU" in exe_name, f"GPU版の実行ファイル名にGPUが含まれていません: {exe_name}"

    def test_cpu_exe_name(self):
        """CPU版の実行ファイル名が正しい"""
        content = read_iss_file(CPU_ISS_FILE)
        exe_name = extract_define(content, "MyAppExeName")

        assert exe_name is not None, "CPU版のMyAppExeNameが定義されていません"
        assert "CPU" in exe_name, f"CPU版の実行ファイル名にCPUが含まれていません: {exe_name}"


class TestEditionSettings:
    """エディション設定の確認"""

    def test_gpu_edition(self):
        """GPU版のエディションがGPU"""
        content = read_iss_file(GPU_ISS_FILE)
        edition = extract_define(content, "MyAppEdition")

        assert edition == "GPU", f"GPU版のエディションが不正: {edition}"

    def test_cpu_edition(self):
        """CPU版のエディションがCPU"""
        content = read_iss_file(CPU_ISS_FILE)
        edition = extract_define(content, "MyAppEdition")

        assert edition == "CPU", f"CPU版のエディションが不正: {edition}"


class TestInstallDirectory:
    """インストールディレクトリの設定確認"""

    def test_gpu_install_dir(self):
        """GPU版のインストールディレクトリが正しい"""
        content = read_iss_file(GPU_ISS_FILE)
        default_dir = extract_setup_value(content, "DefaultDirName")

        assert default_dir is not None
        assert "{autopf}" in default_dir, "Program Filesへのインストールが設定されていません"

    def test_cpu_install_dir(self):
        """CPU版のインストールディレクトリが正しい"""
        content = read_iss_file(CPU_ISS_FILE)
        default_dir = extract_setup_value(content, "DefaultDirName")

        assert default_dir is not None
        assert "{autopf}" in default_dir, "Program Filesへのインストールが設定されていません"

    def test_install_dir_is_same(self):
        """GPU版とCPU版のインストールディレクトリが同じ"""
        gpu_content = read_iss_file(GPU_ISS_FILE)
        cpu_content = read_iss_file(CPU_ISS_FILE)

        gpu_dir = extract_setup_value(gpu_content, "DefaultDirName")
        cpu_dir = extract_setup_value(cpu_content, "DefaultDirName")

        assert gpu_dir == cpu_dir, f"インストールディレクトリが不一致: GPU={gpu_dir}, CPU={cpu_dir}"


class TestWindowsRequirements:
    """Windows要件の設定確認"""

    def test_gpu_requires_win10(self):
        """GPU版がWindows 10以上を要求"""
        content = read_iss_file(GPU_ISS_FILE)
        min_version = extract_setup_value(content, "MinVersion")

        assert min_version is not None
        assert "10" in min_version, f"Windows 10要件が設定されていません: {min_version}"

    def test_cpu_requires_win10(self):
        """CPU版がWindows 10以上を要求"""
        content = read_iss_file(CPU_ISS_FILE)
        min_version = extract_setup_value(content, "MinVersion")

        assert min_version is not None
        assert "10" in min_version, f"Windows 10要件が設定されていません: {min_version}"

    def test_gpu_requires_64bit(self):
        """GPU版が64bit専用"""
        content = read_iss_file(GPU_ISS_FILE)
        arch = extract_setup_value(content, "ArchitecturesAllowed")

        assert arch is not None
        assert "x64" in arch, f"64bit要件が設定されていません: {arch}"

    def test_cpu_requires_64bit(self):
        """CPU版が64bit専用"""
        content = read_iss_file(CPU_ISS_FILE)
        arch = extract_setup_value(content, "ArchitecturesAllowed")

        assert arch is not None
        assert "x64" in arch, f"64bit要件が設定されていません: {arch}"


class TestUninstallSettings:
    """アンインストール設定の確認"""

    def test_gpu_has_uninstall_code(self):
        """GPU版にアンインストールコードがある"""
        content = read_iss_file(GPU_ISS_FILE)

        assert "InitializeUninstall" in content, "GPU版にアンインストール初期化関数がありません"
        assert "UninstallDelete" in content or "[UninstallDelete]" in content, (
            "GPU版にアンインストール削除設定がありません"
        )

    def test_cpu_has_uninstall_code(self):
        """CPU版にアンインストールコードがある"""
        content = read_iss_file(CPU_ISS_FILE)

        assert "InitializeUninstall" in content, "CPU版にアンインストール初期化関数がありません"
        assert "UninstallDelete" in content or "[UninstallDelete]" in content, (
            "CPU版にアンインストール削除設定がありません"
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
