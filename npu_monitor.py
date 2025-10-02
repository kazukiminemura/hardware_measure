#!/usr/bin/env python3
"""
NPU専用監視スクリプト
NPUエンジンの使用率とAI推論活動を専門的に監視します
"""

import time
import psutil
import math
import threading
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

# ----- PDH (Performance Data Helper) via pywin32 -----
try:
    import win32pdh
    HAS_PDH = True
except Exception:
    HAS_PDH = False

# ----- WMI for device detection -----
try:
    import wmi
    HAS_WMI = True
except Exception:
    HAS_WMI = False

REFRESH_SEC = 1.0

class NPUDeviceDetector:
    """NPUデバイス検出・情報取得クラス"""
    
    def __init__(self):
        self.intel_ai_boost_detected = False
        self.npu_devices = []
        self.detection_results = {}
        self._scan_devices()
    
    def _scan_devices(self):
        """システム内のNPUデバイスをスキャン"""
        self.detection_results = {
            'intel_ai_boost': self._detect_intel_ai_boost(),
            'npu_counters': self._check_npu_counters(),
            'npu_devices': self._scan_npu_devices()
        }
        
        self.intel_ai_boost_detected = self.detection_results['intel_ai_boost']
        self.npu_devices = self.detection_results['npu_devices']
    
    def _detect_intel_ai_boost(self) -> bool:
        """Intel AI Boost NPUを検出"""
        if not HAS_WMI:
            return False
        
        try:
            c = wmi.WMI()
            devices = c.Win32_PnPEntity()
            for device in devices:
                device_name = str(getattr(device, 'Name', ''))
                if 'Intel(R) AI Boost' in device_name:
                    return True
        except Exception:
            pass
        return False
    
    def _check_npu_counters(self) -> bool:
        """NPU Performance Countersの利用可能性をチェック"""
        if not HAS_PDH:
            return False
        
        try:
            paths = win32pdh.ExpandCounterPath(r"\NPU Engine(*)\Utilization Percentage")
            return bool(paths)
        except Exception:
            return False
    
    def _scan_npu_devices(self) -> List[Dict[str, str]]:
        """WMI経由でNPU関連デバイスをスキャン"""
        if not HAS_WMI:
            return []
        
        npu_devices = []
        npu_keywords = ['ai boost', 'npu', 'neural', 'ai accelerator', 'inference']
        
        try:
            c = wmi.WMI()
            devices = c.Win32_PnPEntity()
            
            for device in devices:
                device_name = str(getattr(device, 'Name', ''))
                device_desc = str(getattr(device, 'Description', ''))
                device_id = str(getattr(device, 'DeviceID', ''))
                
                for keyword in npu_keywords:
                    if keyword.lower() in device_name.lower() or keyword.lower() in device_desc.lower():
                        npu_devices.append({
                            'name': device_name,
                            'description': device_desc,
                            'device_id': device_id
                        })
                        break
        except Exception:
            pass
        
        return npu_devices
    
    def print_detection_status(self):
        """NPU検出状況を表示"""
        print("=" * 60)
        print(" NPU Detection Results")
        print("=" * 60)
        
        if self.intel_ai_boost_detected:
            print("✓ Intel AI Boost NPU detected")
        else:
            print("✗ Intel AI Boost NPU not detected")
        
        if self.detection_results['npu_counters']:
            print("✓ NPU Performance Counters available")
        else:
            print("✗ NPU Performance Counters not available")
        
        if self.npu_devices:
            print(f"✓ Found {len(self.npu_devices)} NPU-related devices:")
            for i, device in enumerate(self.npu_devices, 1):
                print(f"  {i}. {device['name']}")
                if device['description'] != device['name']:
                    print(f"     Description: {device['description']}")
        else:
            print("✗ No NPU-related devices found")
        
        print()

class NPUPerformanceCollector:
    """NPU Performance Countersデータ収集クラス"""
    
    def __init__(self):
        self.query = None
        self.counters = []
        self._available = False
        self._try_build()
    
    def _try_build(self):
        """NPU Performance Countersの初期化"""
        if not HAS_PDH:
            return
        
        try:
            paths = win32pdh.ExpandCounterPath(r"\NPU Engine(*)\Utilization Percentage")
            if not paths:
                return
            
            self.query = win32pdh.OpenQuery()
            self.counters = []
            
            for path in paths:
                try:
                    handle = win32pdh.AddCounter(self.query, path)
                    self.counters.append((handle, path))
                except Exception:
                    pass
            
            if self.counters:
                win32pdh.CollectQueryData(self.query)
                self._available = True
        except Exception:
            pass
    
    def is_available(self) -> bool:
        """NPU Countersが利用可能かどうか"""
        return self._available
    
    def collect(self) -> Dict[str, float]:
        """NPU使用率データを収集"""
        if not self._available:
            return {}
        
        try:
            time.sleep(0.2)
            win32pdh.CollectQueryData(self.query)
            data = {}
            
            for handle, path in self.counters:
                try:
                    t, val = win32pdh.GetFormattedCounterValue(handle, win32pdh.PDH_FMT_DOUBLE)
                    # インスタンス名を抽出
                    instance = path[path.find('(')+1:path.find(')')] if '(' in path and ')' in path else path
                    
                    # 有効な値のみ追加
                    numeric_val = float(val)
                    if not math.isnan(numeric_val) and numeric_val >= 0:
                        data[instance] = numeric_val
                except Exception:
                    pass
            
            return data
        except Exception:
            return {}

class AIProcessDetector:
    """AI推論プロセス検出クラス"""
    
    def __init__(self):
        self.ai_process_patterns = [
            'onnxruntime', 'directml', 'python', 'pytorch', 'tensorflow',
            'windowsai', 'winml', 'copilot', 'recall', 'studio_effects',
            'ai_assistant', 'chatbot', 'llm'
        ]
        
        self.ai_command_patterns = [
            'onnx', 'torch', 'tensorflow', 'ml', 'ai', 'neural', 'inference'
        ]
    
    def detect_active_ai_processes(self) -> List[Dict[str, Any]]:
        """現在アクティブなAI関連プロセスを検出"""
        ai_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower()
                    
                    is_ai_process = False
                    ai_type = "Unknown"
                    
                    # プロセス名での検出
                    for pattern in self.ai_process_patterns:
                        if pattern in proc_name:
                            is_ai_process = True
                            ai_type = pattern.capitalize()
                            break
                    
                    # Pythonプロセスの場合、コマンドラインを確認
                    if 'python' in proc_name and not is_ai_process:
                        try:
                            cmdline = proc.cmdline()
                            cmdline_str = ' '.join(cmdline).lower()
                            for pattern in self.ai_command_patterns:
                                if pattern in cmdline_str:
                                    is_ai_process = True
                                    ai_type = f"Python ({pattern})"
                                    break
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                    
                    if is_ai_process:
                        ai_processes.append({
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'type': ai_type,
                            'cpu_percent': proc_info['cpu_percent'],
                            'memory_percent': proc_info['memory_percent']
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        return ai_processes

class NPUUsageEstimator:
    """NPU使用率推定クラス"""
    
    def __init__(self, history_size=60):
        self.cpu_baseline = deque(maxlen=history_size)
        self.cpu_during_ai = deque(maxlen=history_size)
        self.ai_process_count = deque(maxlen=history_size)
        
    def update_baseline(self, cpu_percent: float):
        """AI非アクティブ時のCPUベースライン更新"""
        self.cpu_baseline.append(cpu_percent)
    
    def update_ai_activity(self, cpu_percent: float, ai_process_count: int):
        """AI アクティブ時のデータ更新"""
        self.cpu_during_ai.append(cpu_percent)
        self.ai_process_count.append(ai_process_count)
    
    def estimate_npu_usage(self) -> Optional[Dict[str, float]]:
        """NPU使用率を推定"""
        if len(self.cpu_baseline) < 10 or len(self.cpu_during_ai) < 5:
            return None
        
        baseline_avg = sum(self.cpu_baseline) / len(self.cpu_baseline)
        ai_avg = sum(self.cpu_during_ai) / len(self.cpu_during_ai)
        avg_ai_processes = sum(self.ai_process_count) / len(self.ai_process_count)
        
        if baseline_avg <= 0:
            return None
        
        # CPU負荷軽減率を計算
        cpu_reduction = max(0, (baseline_avg - ai_avg) / baseline_avg)
        
        # NPU使用率推定（ヒューリスティック）
        if cpu_reduction > 0.15 and avg_ai_processes > 0:  # 15%以上のCPU負荷軽減
            npu_estimate = min(100, cpu_reduction * 150)  # 推定NPU使用率
            confidence = min(100, cpu_reduction * 200)    # 信頼度
        else:
            npu_estimate = 0
            confidence = 0
        
        return {
            'npu_usage_estimate': npu_estimate,
            'confidence': confidence,
            'cpu_reduction_ratio': cpu_reduction * 100,
            'baseline_cpu': baseline_avg,
            'ai_cpu': ai_avg,
            'avg_ai_processes': avg_ai_processes
        }

class NPUMonitor:
    """NPU専用監視クラス"""
    
    def __init__(self):
        self.device_detector = NPUDeviceDetector()
        self.npu_collector = NPUPerformanceCollector()
        self.ai_detector = AIProcessDetector()
        self.usage_estimator = NPUUsageEstimator()
        
        # 統計データ
        self.stats = {
            'npu_usage': deque(maxlen=300),  # 5分間の履歴
            'ai_activity': deque(maxlen=300),
            'cpu_usage': deque(maxlen=300)
        }
        
        # 監視状態
        self.monitoring = False
        self.monitor_thread = None
    
    def print_header(self):
        """ヘッダー情報を表示"""
        print("=" * 80)
        print(" NPU (Neural Processing Unit) Monitor")
        print("=" * 80)
        print(f" Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 80)
        
        # デバイス検出結果
        self.device_detector.print_detection_status()
        
        # 監視方法の説明
        print("Monitoring Methods:")
        if self.npu_collector.is_available():
            print("✓ Direct NPU Performance Counters")
        else:
            print("✗ Direct NPU Performance Counters (using estimation)")
        print("✓ AI Process Detection")
        print("✓ CPU Usage Pattern Analysis")
        print("✓ NPU Usage Estimation")
        print()
    
    def collect_metrics(self) -> Dict[str, Any]:
        """各種メトリクスを収集"""
        # NPU パフォーマンスカウンター
        npu_data = self.npu_collector.collect()
        
        # AI プロセス検出
        ai_processes = self.ai_detector.detect_active_ai_processes()
        
        # システムメトリクス
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_percent = psutil.virtual_memory().percent
        
        # NPU使用率計算
        npu_usage = 0.0
        npu_engines = []
        
        if npu_data:
            # 直接計測値がある場合
            npu_values = list(npu_data.values())
            if npu_values:
                npu_usage = max(npu_values)  # 最大値を採用
                npu_engines = [(name, value) for name, value in npu_data.items()]
        
        # 使用率推定器の更新
        if ai_processes:
            self.usage_estimator.update_ai_activity(cpu_percent, len(ai_processes))
        else:
            self.usage_estimator.update_baseline(cpu_percent)
        
        # 推定値取得
        npu_estimate = self.usage_estimator.estimate_npu_usage()
        
        # データ統計更新
        timestamp = time.time()
        self.stats['npu_usage'].append((timestamp, npu_usage))
        self.stats['ai_activity'].append((timestamp, len(ai_processes)))
        self.stats['cpu_usage'].append((timestamp, cpu_percent))
        
        return {
            'timestamp': timestamp,
            'npu_usage': npu_usage,
            'npu_engines': npu_engines,
            'npu_estimate': npu_estimate,
            'ai_processes': ai_processes,
            'cpu_percent': cpu_percent,
            'memory_percent': memory_percent
        }
    
    def display_metrics(self, metrics: Dict[str, Any]):
        """メトリクスを表示"""
        timestamp = datetime.fromtimestamp(metrics['timestamp'])
        
        # 基本情報行
        print(f"\n[{timestamp.strftime('%H:%M:%S')}] " + "-" * 65)
        
        # NPU使用率
        if metrics['npu_usage'] > 0:
            print(f"NPU Usage : {metrics['npu_usage']:6.1f}% (Direct measurement)")
            if metrics['npu_engines']:
                engines_str = ", ".join([f"{name}:{val:.1f}%" for name, val in metrics['npu_engines'][:3]])
                print(f"            Engines: {engines_str}")
        else:
            print("NPU Usage : n/a (Direct measurement not available)")
        
        # NPU推定値
        if metrics['npu_estimate']:
            est = metrics['npu_estimate']
            print(f"NPU Est.  : {est['npu_usage_estimate']:6.1f}% "
                  f"(Confidence: {est['confidence']:.0f}%, "
                  f"CPU reduction: {est['cpu_reduction_ratio']:.1f}%)")
        else:
            print("NPU Est.  :    n/a (Insufficient data)")
        
        # AI プロセス
        ai_count = len(metrics['ai_processes'])
        if ai_count > 0:
            print(f"AI Proc.  : {ai_count:3d} active processes")
            for proc in metrics['ai_processes'][:3]:  # 最初の3つを表示
                print(f"            {proc['name']} (PID:{proc['pid']}) - "
                      f"CPU:{proc['cpu_percent']:.1f}%, Type:{proc['type']}")
            if ai_count > 3:
                print(f"            ... and {ai_count - 3} more")
        else:
            print("AI Proc.  :   0 active processes")
        
        # システムリソース
        print(f"System    : CPU {metrics['cpu_percent']:5.1f}%, "
              f"Memory {metrics['memory_percent']:5.1f}%")
    
    def calculate_statistics(self, minutes: int = 5) -> Dict[str, Any]:
        """指定時間内の統計を計算"""
        cutoff_time = time.time() - (minutes * 60)
        
        # NPU使用率統計
        recent_npu = [(t, v) for t, v in self.stats['npu_usage'] if t > cutoff_time]
        npu_values = [v for t, v in recent_npu if v > 0]
        
        # AI活動統計
        recent_ai = [(t, v) for t, v in self.stats['ai_activity'] if t > cutoff_time]
        ai_active_ratio = len([v for t, v in recent_ai if v > 0]) / len(recent_ai) if recent_ai else 0
        
        # CPU統計
        recent_cpu = [(t, v) for t, v in self.stats['cpu_usage'] if t > cutoff_time]
        cpu_values = [v for t, v in recent_cpu]
        
        return {
            'period_minutes': minutes,
            'npu_avg': sum(npu_values) / len(npu_values) if npu_values else 0,
            'npu_max': max(npu_values) if npu_values else 0,
            'ai_active_ratio': ai_active_ratio * 100,
            'cpu_avg': sum(cpu_values) / len(cpu_values) if cpu_values else 0,
            'sample_count': len(recent_npu)
        }
    
    def start_monitoring(self):
        """監視を開始"""
        self.print_header()
        
        # CPU priming
        psutil.cpu_percent(interval=None)
        
        print("Starting NPU monitoring... (Press Ctrl+C to stop)")
        print()
        
        try:
            while True:
                metrics = self.collect_metrics()
                self.display_metrics(metrics)
                
                # 5分ごとに統計表示
                if len(self.stats['npu_usage']) % (5 * 60) == 0 and len(self.stats['npu_usage']) > 0:
                    stats = self.calculate_statistics(5)
                    print(f"\n--- 5-min Summary ---")
                    print(f"NPU Avg: {stats['npu_avg']:.1f}%, Max: {stats['npu_max']:.1f}%")
                    print(f"AI Active: {stats['ai_active_ratio']:.1f}% of time")
                    print(f"CPU Avg: {stats['cpu_avg']:.1f}%")
                    print(f"Samples: {stats['sample_count']}")
                
                time.sleep(REFRESH_SEC)
                
        except KeyboardInterrupt:
            print("\n\nMonitoring stopped.")
            
            # 最終統計表示
            if len(self.stats['npu_usage']) > 0:
                final_stats = self.calculate_statistics(len(self.stats['npu_usage']) // 60 + 1)
                print("\n=== Final Statistics ===")
                print(f"Total monitoring time: ~{final_stats['sample_count']} seconds")
                print(f"NPU Average usage: {final_stats['npu_avg']:.1f}%")
                print(f"NPU Maximum usage: {final_stats['npu_max']:.1f}%")
                print(f"AI activity ratio: {final_stats['ai_active_ratio']:.1f}%")
                print(f"CPU Average usage: {final_stats['cpu_avg']:.1f}%")

def main():
    """メイン関数"""
    print("NPU (Neural Processing Unit) Monitor")
    print("Specialized monitoring for NPU engines and AI inference activity")
    print()
    
    monitor = NPUMonitor()
    monitor.start_monitoring()

if __name__ == "__main__":
    main()