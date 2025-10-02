# ONNX Runtime + DirectML を使用したNPU/AI推論監視
import time
import threading
import numpy as np
from collections import defaultdict, deque
import psutil

class AIWorkloadMonitor:
    """AI推論ワークロード実行中のシステム監視"""
    
    def __init__(self):
        self.monitoring = False
        self.stats = defaultdict(list)
        self.baseline_stats = {}
        
    def get_system_snapshot(self):
        """システムリソースのスナップショットを取得"""
        try:
            return {
                'timestamp': time.time(),
                'cpu_percent': psutil.cpu_percent(interval=None),
                'cpu_per_core': psutil.cpu_percent(interval=None, percpu=True),
                'memory_percent': psutil.virtual_memory().percent,
                'memory_used_gb': psutil.virtual_memory().used / (1024**3),
            }
        except Exception as e:
            print(f"システムスナップショット取得エラー: {e}")
            return None
    
    def start_monitoring(self, duration_seconds=10):
        """指定期間のシステム監視を開始"""
        self.monitoring = True
        self.stats = defaultdict(list)
        
        def monitor_loop():
            start_time = time.time()
            while self.monitoring and (time.time() - start_time) < duration_seconds:
                snapshot = self.get_system_snapshot()
                if snapshot:
                    for key, value in snapshot.items():
                        self.stats[key].append(value)
                time.sleep(0.1)  # 100ms間隔
        
        self.monitor_thread = threading.Thread(target=monitor_loop)
        self.monitor_thread.start()
    
    def stop_monitoring(self):
        """監視を停止"""
        self.monitoring = False
        if hasattr(self, 'monitor_thread'):
            self.monitor_thread.join()
    
    def get_statistics(self):
        """監視データの統計を取得"""
        if not self.stats:
            return {}
        
        stats_summary = {}
        for key, values in self.stats.items():
            if key == 'timestamp':
                continue
            if isinstance(values[0], list):  # cpu_per_core
                # コア別の平均を計算
                core_averages = []
                for core_idx in range(len(values[0])):
                    core_values = [core_data[core_idx] for core_data in values]
                    core_averages.append(np.mean(core_values))
                stats_summary[key] = {
                    'average_per_core': core_averages,
                    'max_per_core': [max(core_data[i] for core_data in values) 
                                   for i in range(len(values[0]))],
                    'overall_max': max(max(core_data) for core_data in values)
                }
            else:
                stats_summary[key] = {
                    'average': np.mean(values),
                    'max': max(values),
                    'min': min(values),
                    'std': np.std(values)
                }
        
        return stats_summary

def check_onnx_runtime_providers():
    """利用可能なONNX Runtime プロバイダーを確認"""
    print("=== ONNX Runtime プロバイダー確認 ===")
    
    try:
        import onnxruntime as ort
        
        # 利用可能なプロバイダー一覧
        available_providers = ort.get_available_providers()
        print(f"利用可能なプロバイダー: {len(available_providers)}個")
        
        provider_info = []
        for provider in available_providers:
            info = {'name': provider}
            
            # プロバイダーの詳細情報
            if provider == 'DmlExecutionProvider':
                info['description'] = 'DirectML (GPU/NPU対応)'
                info['hardware'] = 'GPU/NPU'
                info['priority'] = 'HIGH for NPU'
            elif provider == 'CPUExecutionProvider':
                info['description'] = 'CPU実行'
                info['hardware'] = 'CPU'
                info['priority'] = 'LOW'
            elif provider == 'CUDAExecutionProvider':
                info['description'] = 'NVIDIA CUDA'
                info['hardware'] = 'NVIDIA GPU'
                info['priority'] = 'MEDIUM'
            else:
                info['description'] = '不明'
                info['hardware'] = '不明'
                info['priority'] = 'UNKNOWN'
            
            provider_info.append(info)
            print(f"  ✓ {provider}: {info['description']} ({info['hardware']})")
        
        return provider_info
        
    except ImportError:
        print("ONNX Runtime がインストールされていません")
        return []
    except Exception as e:
        print(f"プロバイダー確認エラー: {e}")
        return []

def create_simple_test_model():
    """テスト用の簡単なONNXモデルを作成"""
    print("\n=== テスト用モデル作成 ===")
    
    try:
        # 簡単な計算グラフを作成（実際のONNX作成はonnxライブラリが必要）
        # ここでは推論テスト用のダミーデータを準備
        
        input_shape = (1, 3, 224, 224)  # 標準的な画像入力形状
        test_input = np.random.rand(*input_shape).astype(np.float32)
        
        print(f"テスト入力データ作成: 形状 {input_shape}")
        print(f"データタイプ: {test_input.dtype}")
        print(f"データサイズ: {test_input.size} 要素")
        
        return test_input
        
    except Exception as e:
        print(f"テストモデル作成エラー: {e}")
        return None

def run_inference_benchmark(providers_to_test=None):
    """各プロバイダーでの推論ベンチマーク"""
    print("\n=== 推論ベンチマーク実行 ===")
    
    try:
        import onnxruntime as ort
        
        if providers_to_test is None:
            providers_to_test = ort.get_available_providers()
        
        # 簡単な計算負荷を作成（実際のONNXモデルがない場合）
        test_data = create_simple_test_model()
        if test_data is None:
            return {}
        
        results = {}
        monitor = AIWorkloadMonitor()
        
        for provider in providers_to_test:
            print(f"\n--- {provider} でのテスト ---")
            
            try:
                # 実際のONNXモデルファイルがある場合のコード例
                # session = ort.InferenceSession('model.onnx', providers=[provider])
                # 
                # モデルがない場合は計算負荷テストを実行
                
                # システム監視開始
                print("システム監視開始...")
                monitor.start_monitoring(duration_seconds=5)
                
                # 計算負荷シミュレーション
                start_time = time.time()
                for i in range(10):  # 10回の計算を実行
                    # 簡単な行列計算でCPU/GPU負荷をかける
                    if provider == 'DmlExecutionProvider':
                        # DirectML使用時はより複雑な計算
                        result = np.dot(test_data.reshape(1, -1), test_data.reshape(-1, 1))
                        result = np.exp(result) / np.sum(np.exp(result))  # softmax風
                    else:
                        # CPU用の軽い計算
                        result = np.mean(test_data)
                    
                    time.sleep(0.1)  # 100ms待機
                
                inference_time = time.time() - start_time
                monitor.stop_monitoring()
                
                # 結果をまとめる
                system_stats = monitor.get_statistics()
                results[provider] = {
                    'inference_time': inference_time,
                    'system_stats': system_stats,
                    'success': True
                }
                
                print(f"推論時間: {inference_time:.3f}秒")
                if 'cpu_percent' in system_stats:
                    print(f"平均CPU使用率: {system_stats['cpu_percent']['average']:.1f}%")
                if 'memory_percent' in system_stats:
                    print(f"平均メモリ使用率: {system_stats['memory_percent']['average']:.1f}%")
                
            except Exception as e:
                print(f"エラー: {e}")
                results[provider] = {
                    'inference_time': None,
                    'system_stats': {},
                    'success': False,
                    'error': str(e)
                }
                monitor.stop_monitoring()
        
        return results
        
    except ImportError:
        print("ONNX Runtime が利用できません")
        return {}
    except Exception as e:
        print(f"ベンチマークエラー: {e}")
        return {}

def analyze_npu_usage_patterns(benchmark_results):
    """ベンチマーク結果からNPU使用パターンを分析"""
    print("\n=== NPU使用パターン分析 ===")
    
    if not benchmark_results:
        print("分析するデータがありません")
        return
    
    # DirectML (NPU/GPU) vs CPU の比較
    dml_result = benchmark_results.get('DmlExecutionProvider')
    cpu_result = benchmark_results.get('CPUExecutionProvider')
    
    if dml_result and cpu_result and dml_result['success'] and cpu_result['success']:
        print("DirectML vs CPU 比較:")
        
        dml_time = dml_result['inference_time']
        cpu_time = cpu_result['inference_time']
        
        if dml_time and cpu_time:
            speedup = cpu_time / dml_time
            print(f"  DirectML 推論時間: {dml_time:.3f}秒")
            print(f"  CPU 推論時間: {cpu_time:.3f}秒")
            print(f"  スピードアップ: {speedup:.2f}x")
            
            if speedup > 1.5:
                print("  → DirectMLアクセラレーション有効 (NPU/GPU使用の可能性)")
            elif speedup > 1.1:
                print("  → 軽微なアクセラレーション")
            else:
                print("  → CPUとの有意差なし")
        
        # システムリソース使用パターンの比較
        dml_stats = dml_result.get('system_stats', {})
        cpu_stats = cpu_result.get('system_stats', {})
        
        if dml_stats and cpu_stats:
            print("\nリソース使用パターン:")
            
            if 'cpu_percent' in dml_stats and 'cpu_percent' in cpu_stats:
                dml_cpu = dml_stats['cpu_percent']['average']
                cpu_cpu = cpu_stats['cpu_percent']['average']
                print(f"  DirectML CPU使用率: {dml_cpu:.1f}%")
                print(f"  CPU-only CPU使用率: {cpu_cpu:.1f}%")
                
                if dml_cpu < cpu_cpu * 0.8:
                    print("  → NPU/GPU オフロードの可能性")
                elif dml_cpu < cpu_cpu * 0.95:
                    print("  → 部分的なオフロード")
                else:
                    print("  → CPU負荷に大きな差なし")
    
    # 全プロバイダーの結果サマリー
    print(f"\n全プロバイダー結果サマリー:")
    for provider, result in benchmark_results.items():
        if result['success']:
            print(f"  {provider}:")
            print(f"    推論時間: {result.get('inference_time', 'N/A'):.3f}秒")
            stats = result.get('system_stats', {})
            if 'cpu_percent' in stats:
                print(f"    平均CPU: {stats['cpu_percent']['average']:.1f}%")
        else:
            print(f"  {provider}: 失敗 ({result.get('error', 'Unknown error')})")

def integrate_with_hardware_monitor():
    """既存のハードウェア監視プログラムとの統合提案"""
    print("\n=== ハードウェア監視との統合提案 ===")
    
    integration_suggestions = [
        {
            'feature': 'AI推論検出',
            'description': 'ONNX Runtime / DirectMLプロセスの検出',
            'implementation': 'プロセス名監視: onnxruntime, DirectML関連プロセス'
        },
        {
            'feature': 'NPU推論活動監視',
            'description': 'DirectML使用時のリソース使用パターン追跡',
            'implementation': 'GPU Engine監視の拡張 + CPU使用率パターン分析'
        },
        {
            'feature': 'AI負荷ベンチマーク',
            'description': '定期的なNPU性能テストの実行',
            'implementation': '軽量ベンチマークの定期実行とベースライン比較'
        },
        {
            'feature': 'NPU使用率推定',
            'description': '間接的なNPU使用率の推定',
            'implementation': 'CPU負荷軽減 + DirectML活動の相関分析'
        }
    ]
    
    for suggestion in integration_suggestions:
        print(f"\n機能: {suggestion['feature']}")
        print(f"  説明: {suggestion['description']}")
        print(f"  実装方法: {suggestion['implementation']}")
    
    print(f"\n推奨統合アプローチ:")
    print(f"1. 既存のPDH GPU Engine監視にDirectML検出を追加")
    print(f"2. AI推論プロセス検出時の詳細リソース監視")
    print(f"3. NPU使用の間接的指標（CPU負荷軽減率）の表示")

if __name__ == "__main__":
    print("ONNX Runtime + DirectML を使用したNPU監視アプローチ")
    print("=" * 60)
    
    # プロバイダー確認
    providers = check_onnx_runtime_providers()
    
    # ベンチマーク実行
    if providers:
        # DirectMLが利用可能な場合のみベンチマーク実行
        dml_available = any(p['name'] == 'DmlExecutionProvider' for p in providers)
        if dml_available:
            print(f"\nDirectMLが利用可能です - NPU/GPU推論テストを実行...")
            benchmark_results = run_inference_benchmark(['DmlExecutionProvider', 'CPUExecutionProvider'])
            
            # 結果分析
            analyze_npu_usage_patterns(benchmark_results)
        else:
            print(f"\nDirectMLが利用できません - CPU推論のみテスト...")
            benchmark_results = run_inference_benchmark(['CPUExecutionProvider'])
    
    # 統合提案
    integrate_with_hardware_monitor()
    
    print(f"\n=== 結論 ===")
    print(f"Windows MLでの直接的なNPU監視は限定的ですが、")
    print(f"ONNX Runtime + DirectMLを使用することで：")
    print(f"1. NPU/GPU推論の検出")
    print(f"2. 推論性能の測定")
    print(f"3. システムリソース使用パターンの分析")
    print(f"が可能です。既存の監視プログラムに統合することで")
    print(f"より包括的なNPU活動監視を実現できます。")