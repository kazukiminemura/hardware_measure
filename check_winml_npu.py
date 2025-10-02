# Windows ML (WinML) を使用したNPU監視の調査
import time
import threading
from collections import defaultdict
import json

def check_winml_availability():
    """Windows ML の利用可能性を確認"""
    print("=== Windows ML 利用可能性確認 ===")
    
    try:
        # Windows Runtime (WinRT) を使用してWindows MLにアクセス
        import winrt
        from winrt.windows.ai.machinelearning import LearningModel, LearningModelDevice, LearningModelDeviceKind
        print("✓ Windows ML (WinML) が利用可能です")
        return True
    except ImportError:
        print("✗ winrt パッケージがインストールされていません")
        print("  pip install winrt でインストールしてください")
        return False
    except Exception as e:
        print(f"✗ Windows ML 初期化エラー: {e}")
        return False

def enumerate_ml_devices():
    """利用可能なML推論デバイスを列挙"""
    print("\n=== 利用可能なML推論デバイス ===")
    
    try:
        from winrt.windows.ai.machinelearning import LearningModelDevice, LearningModelDeviceKind
        
        # 各デバイスタイプを確認
        device_types = [
            (LearningModelDeviceKind.CPU, "CPU"),
            (LearningModelDeviceKind.DIRECTORY_X, "DirectX (GPU)"),
        ]
        
        # NPU サポートを確認
        try:
            # Windows 11の新しいバージョンではNPUサポートが追加される可能性
            npu_device = LearningModelDevice.create_from_direct3_d11_device(None)  # NPU検出の試行
            device_types.append((None, "NPU (experimental)"))
        except:
            pass
        
        detected_devices = []
        
        for device_kind, name in device_types:
            try:
                if device_kind is not None:
                    device = LearningModelDevice.create(device_kind)
                    detected_devices.append({
                        'kind': device_kind,
                        'name': name,
                        'device': device
                    })
                    print(f"✓ {name}: 利用可能")
                else:
                    print(f"? {name}: 検出試行中...")
            except Exception as e:
                print(f"✗ {name}: 利用不可 ({e})")
        
        return detected_devices
        
    except ImportError:
        print("Windows ML モジュールが利用できません")
        return []
    except Exception as e:
        print(f"デバイス列挙エラー: {e}")
        return []

def create_simple_onnx_model():
    """簡単なONNXモデルを作成（NPU負荷テスト用）"""
    print("\n=== 簡単なONNXモデル作成 ===")
    
    try:
        import numpy as np
        
        # NumPyで簡単なモデルデータを作成
        # 実際のONNXモデル作成にはonnxライブラリが必要ですが、
        # ここではWindows MLテスト用の疑似データを作成
        print("簡単なテストデータを準備中...")
        
        # テスト用の入力データ
        test_input = np.random.rand(1, 3, 224, 224).astype(np.float32)
        print(f"テスト入力データ形状: {test_input.shape}")
        
        return test_input
        
    except ImportError:
        print("NumPy が必要です: pip install numpy")
        return None
    except Exception as e:
        print(f"モデル作成エラー: {e}")
        return None

def monitor_system_during_ml_inference():
    """ML推論実行中のシステムリソース監視"""
    print("\n=== ML推論中のシステム監視 ===")
    
    try:
        import psutil
        import time
        
        def get_system_stats():
            return {
                'cpu_percent': psutil.cpu_percent(interval=None),
                'memory_percent': psutil.virtual_memory().percent,
                'timestamp': time.time()
            }
        
        # ML推論前のベースライン
        print("ベースライン測定中...")
        baseline_stats = []
        for i in range(5):
            baseline_stats.append(get_system_stats())
            time.sleep(0.2)
        
        avg_baseline_cpu = sum(s['cpu_percent'] for s in baseline_stats) / len(baseline_stats)
        avg_baseline_mem = sum(s['memory_percent'] for s in baseline_stats) / len(baseline_stats)
        
        print(f"ベースライン CPU: {avg_baseline_cpu:.1f}%")
        print(f"ベースライン メモリ: {avg_baseline_mem:.1f}%")
        
        return {
            'baseline_cpu': avg_baseline_cpu,
            'baseline_memory': avg_baseline_mem,
            'baseline_stats': baseline_stats
        }
        
    except ImportError:
        print("psutil が必要です: pip install psutil")
        return None
    except Exception as e:
        print(f"システム監視エラー: {e}")
        return None

def attempt_npu_detection_via_winml():
    """Windows ML経由でのNPU検出試行"""
    print("\n=== Windows ML経由NPU検出 ===")
    
    try:
        from winrt.windows.ai.machinelearning import LearningModelDevice, LearningModelDeviceKind
        
        # 利用可能なすべてのデバイスを試行
        device_tests = [
            ("CPU", LearningModelDeviceKind.CPU),
            ("DirectX", LearningModelDeviceKind.DIRECTORY_X),
        ]
        
        results = {}
        
        for name, kind in device_tests:
            try:
                device = LearningModelDevice.create(kind)
                # デバイス情報を取得
                device_info = {
                    'available': True,
                    'kind': str(kind),
                    'adapter_id': getattr(device, 'adapter_id', 'N/A') if hasattr(device, 'adapter_id') else 'N/A'
                }
                results[name] = device_info
                print(f"✓ {name}: {device_info}")
            except Exception as e:
                results[name] = {'available': False, 'error': str(e)}
                print(f"✗ {name}: {e}")
        
        # NPU関連のデバイス情報を探す
        print("\nNPU関連デバイス検索:")
        try:
            import wmi
            c = wmi.WMI()
            devices = c.Win32_PnPEntity()
            npu_devices = []
            
            for device in devices:
                device_name = str(getattr(device, 'Name', ''))
                if any(keyword in device_name.lower() for keyword in ['ai boost', 'npu', 'neural']):
                    npu_devices.append(device_name)
            
            if npu_devices:
                print(f"検出されたNPU関連デバイス: {len(npu_devices)}個")
                for device in npu_devices:
                    print(f"  - {device}")
                results['npu_devices'] = npu_devices
            else:
                print("NPU関連デバイスが見つかりませんでした")
                results['npu_devices'] = []
                
        except Exception as e:
            print(f"NPUデバイス検索エラー: {e}")
            results['npu_devices'] = []
        
        return results
        
    except Exception as e:
        print(f"Windows ML NPU検出エラー: {e}")
        return {}

def suggest_winml_monitoring_approach():
    """Windows ML を使用したNPU監視アプローチの提案"""
    print("\n=== Windows ML NPU監視アプローチ ===")
    
    approaches = [
        {
            'name': '1. DirectML バックエンド監視',
            'description': 'DirectMLを使用したML推論時のGPU/NPU使用量を間接的に監視',
            'feasibility': 'HIGH',
            'requirements': ['Windows ML', 'DirectML対応モデル', 'パフォーマンスカウンター']
        },
        {
            'name': '2. 推論時間ベース監視',
            'description': 'NPU vs CPU/GPU での推論時間差を利用してNPU活用度を推定',
            'feasibility': 'MEDIUM',
            'requirements': ['複数デバイスでの推論比較', 'ベンチマークモデル']
        },
        {
            'name': '3. 電力消費パターン監視',
            'description': 'NPU使用時の電力消費パターンの変化を監視',
            'feasibility': 'LOW',
            'requirements': ['詳細な電力監視API', 'ベースライン測定']
        },
        {
            'name': '4. プロセス別リソース監視',
            'description': 'ML推論プロセスのリソース使用パターンからNPU使用を推定',
            'feasibility': 'MEDIUM',
            'requirements': ['プロセス監視', 'ML推論プロセス識別']
        }
    ]
    
    for approach in approaches:
        print(f"\n{approach['name']}")
        print(f"  説明: {approach['description']}")
        print(f"  実現性: {approach['feasibility']}")
        print(f"  要件: {', '.join(approach['requirements'])}")
    
    print(f"\n推奨アプローチ:")
    print(f"1. まず DirectML バックエンドでの GPU Engine 監視を強化")
    print(f"2. Windows ML 推論実行時のシステムリソース変化を測定")
    print(f"3. NPU対応モデルでの推論性能をベンチマーク")

if __name__ == "__main__":
    print("Windows ML を使用したNPU監視可能性調査")
    print("=" * 60)
    
    # 基本的な利用可能性確認
    winml_available = check_winml_availability()
    
    if winml_available:
        # デバイス列挙
        devices = enumerate_ml_devices()
        
        # NPU検出試行
        npu_results = attempt_npu_detection_via_winml()
        
        # システム監視テスト
        monitoring_results = monitor_system_during_ml_inference()
        
        # テストデータ作成
        test_data = create_simple_onnx_model()
        
    # 監視アプローチの提案
    suggest_winml_monitoring_approach()
    
    print("\n=== 次のステップ ===")
    print("1. winrt パッケージのインストール: pip install winrt")
    print("2. 簡単なONNXモデルでの推論テスト")
    print("3. DirectML使用時のGPU Engineパフォーマンス監視")
    print("4. NPU対応アプリケーションでの実測値比較")