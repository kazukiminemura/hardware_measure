# NPU パフォーマンスカウンターの確認スクリプト
import os
import subprocess

def check_performance_counters():
    """利用可能なパフォーマンスカウンターをチェック"""
    print("=== パフォーマンスカウンターの確認 ===")
    
    # typeperf コマンドでカウンターリストを取得
    try:
        # NPU関連のカウンターを検索
        print("\n1. NPU関連カウンターの検索:")
        result = subprocess.run(['typeperf', '-q'], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            npu_counters = [line for line in lines if 'NPU' in line.upper()]
            if npu_counters:
                print(f"見つかったNPUカウンター: {len(npu_counters)}個")
                for counter in npu_counters[:10]:  # 最初の10個を表示
                    print(f"  {counter}")
                if len(npu_counters) > 10:
                    print(f"  ... 他 {len(npu_counters) - 10}個")
            else:
                print("NPUカウンターが見つかりませんでした")
        else:
            print(f"typeperf エラー: {result.stderr}")
            
        # GPU関連カウンターも確認（比較用）
        print("\n2. GPU関連カウンターの検索:")
        if result.returncode == 0:
            gpu_counters = [line for line in lines if 'GPU' in line.upper()]
            if gpu_counters:
                print(f"見つかったGPUカウンター: {len(gpu_counters)}個")
                for counter in gpu_counters[:5]:  # 最初の5個を表示
                    print(f"  {counter}")
            else:
                print("GPUカウンターが見つかりませんでした")
                
    except subprocess.TimeoutExpired:
        print("typeperf コマンドがタイムアウトしました")
    except FileNotFoundError:
        print("typeperf コマンドが見つかりません")
    except Exception as e:
        print(f"エラー: {e}")

def check_system_info():
    """システム情報を確認"""
    print("\n=== システム情報 ===")
    
    try:
        # Windows バージョン
        result = subprocess.run(['ver'], shell=True, capture_output=True, text=True)
        print(f"Windows バージョン: {result.stdout.strip()}")
        
        # システム情報
        result = subprocess.run(['systeminfo'], capture_output=True, text=True, timeout=30)
        if result.returncode == 0:
            lines = result.stdout.split('\n')
            for line in lines:
                if any(keyword in line.lower() for keyword in ['processor', 'system model', 'system manufacturer']):
                    print(line.strip())
                    
    except Exception as e:
        print(f"システム情報取得エラー: {e}")

def check_with_pywin32():
    """pywin32でのNPUカウンター確認"""
    print("\n=== pywin32でのカウンター確認 ===")
    
    try:
        import win32pdh
        
        # NPU Engine カウンターの存在確認
        npu_patterns = [
            r"\NPU Engine(*)\Utilization Percentage",
            r"\NPU Engine(*)\*",
            r"\Neural Processing Unit(*)\*",
            r"\AI Accelerator(*)\*"
        ]
        
        for pattern in npu_patterns:
            try:
                print(f"\nパターン '{pattern}' をチェック中...")
                paths = win32pdh.ExpandCounterPath(pattern)
                if paths:
                    print(f"  見つかったパス: {len(paths)}個")
                    for path in paths[:5]:  # 最初の5個を表示
                        print(f"    {path}")
                    if len(paths) > 5:
                        print(f"    ... 他 {len(paths) - 5}個")
                else:
                    print("  パスが見つかりませんでした")
            except Exception as e:
                print(f"  エラー: {e}")
                
    except ImportError:
        print("win32pdh がインストールされていません")
    except Exception as e:
        print(f"エラー: {e}")

if __name__ == "__main__":
    check_system_info()
    check_performance_counters()
    check_with_pywin32()
    
    print("\n=== 推奨事項 ===")
    print("1. NPUカウンターが見つからない場合:")
    print("   - Windows 11 24H2以降が必要な場合があります")
    print("   - NPU対応ハードウェアが必要です")
    print("   - デバイスドライバが最新か確認してください")
    print("2. 代替案:")
    print("   - タスクマネージャーでNPUが表示されるか確認")
    print("   - デバイスマネージャーでNPUデバイスを確認")
    print("   - WMI (Windows Management Instrumentation) での監視を検討")