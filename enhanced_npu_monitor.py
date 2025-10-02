#!/usr/bin/env python3
"""
Enhanced NPU Monitor - より詳細なNPU監視スクリプト
NPUエンジンの使用率、AI推論活動、システムリソースを包括的に監視
"""

import time
import psutil
import math
import threading
import subprocess
import json
from collections import defaultdict, deque
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

# ----- Dependencies -----
try:
    import win32pdh
    HAS_PDH = True
except Exception:
    HAS_PDH = False

try:
    import wmi
    HAS_WMI = True
except Exception:
    HAS_WMI = False

REFRESH_SEC = 1.0

class EnhancedNPUDetector:
    """拡張NPUデバイス検出クラス"""
    
    def __init__(self):
        self.detection_results = {}
        self.npu_devices = []
        self.system_info = {}
        self._perform_detection()
    
    def _perform_detection(self):
        """包括的なNPU検出を実行"""
        self.detection_results = {
            'intel_ai_boost': self._detect_intel_ai_boost(),
            'npu_counters': self._check_npu_counters(),
            'task_manager_npu': self._check_task_manager_npu(),
            'directml_support': self._check_directml_support(),
            'npu_devices': self._scan_all_npu_devices(),
            'system_info': self._get_system_info()
        }
        
        self.npu_devices = self.detection_results['npu_devices']
        self.system_info = self.detection_results['system_info']
    
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
    
    def _check_npu_counters(self) -> Dict[str, Any]:
        """NPU Performance Countersの詳細チェック"""
        if not HAS_PDH:
            return {'available': False, 'reason': 'PDH not available'}
        
        npu_patterns = [
            r"\NPU Engine(*)\Utilization Percentage",
            r"\NPU Engine(*)\*",
            r"\Intel AI Boost(*)\*",
            r"\Neural Processing Unit(*)\*"
        ]
        
        results = {'available': False, 'patterns_found': []}
        
        for pattern in npu_patterns:
            try:
                paths = win32pdh.ExpandCounterPath(pattern)
                if paths:
                    results['patterns_found'].append({
                        'pattern': pattern,
                        'count': len(paths),
                        'paths': paths[:5]  # 最初の5個のみ
                    })
                    results['available'] = True
            except Exception:
                pass
        
        return results
    
    def _check_task_manager_npu(self) -> bool:
        """タスクマネージャーでのNPU表示確認"""
        try:
            # PowerShellでタスクマネージャー相当の情報を取得
            result = subprocess.run([
                'powershell', '-Command',
                'Get-Counter -ListSet "*NPU*" -ErrorAction SilentlyContinue | Select-Object CounterSetName'
            ], capture_output=True, text=True, timeout=10)
            
            return 'NPU' in result.stdout
        except Exception:
            return False
    
    def _check_directml_support(self) -> Dict[str, Any]:
        """DirectMLサポートの確認"""
        try:
            # DirectML DLLの存在確認
            import os
            system32_path = os.path.join(os.environ.get('WINDIR', 'C:\\Windows'), 'System32')
            directml_dll = os.path.join(system32_path, 'DirectML.dll')
            
            return {
                'dll_exists': os.path.exists(directml_dll),
                'path': directml_dll if os.path.exists(directml_dll) else None
            }
        except Exception:
            return {'dll_exists': False, 'path': None}
    
    def _scan_all_npu_devices(self) -> List[Dict[str, str]]:
        """包括的なNPU関連デバイススキャン"""
        if not HAS_WMI:
            return []
        
        npu_devices = []
        
        # より広範囲なキーワードで検索
        npu_keywords = [
            'ai boost', 'npu', 'neural', 'ai accelerator', 'inference',
            'machine learning', 'deep learning', 'qualcomm', 'snapdragon',
            'intel ai', 'amd ai', 'neural processor', 'ai engine'
        ]
        
        try:
            c = wmi.WMI()
            
            # 複数のWMIクラスから検索
            wmi_classes = ['Win32_PnPEntity', 'Win32_SystemDevice', 'Win32_Processor']
            
            for wmi_class in wmi_classes:
                try:
                    devices = getattr(c, wmi_class)()
                    for device in devices:
                        device_name = str(getattr(device, 'Name', '')).lower()
                        device_desc = str(getattr(device, 'Description', '')).lower()
                        device_id = str(getattr(device, 'DeviceID', ''))
                        
                        for keyword in npu_keywords:
                            if keyword in device_name or keyword in device_desc:
                                npu_devices.append({
                                    'name': str(getattr(device, 'Name', '')),
                                    'description': str(getattr(device, 'Description', '')),
                                    'device_id': device_id,
                                    'class': wmi_class,
                                    'keyword_matched': keyword
                                })
                                break
                except Exception:
                    continue
        except Exception:
            pass
        
        return npu_devices
    
    def _get_system_info(self) -> Dict[str, str]:
        """システム情報取得"""
        try:
            result = subprocess.run([
                'wmic', 'computersystem', 'get', 'Model,Manufacturer', '/format:csv'
            ], capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                if len(lines) >= 2:
                    headers = lines[0].split(',')
                    data = lines[1].split(',')
                    if len(data) >= 3:
                        return {
                            'manufacturer': data[1] if len(data) > 1 else 'Unknown',
                            'model': data[2] if len(data) > 2 else 'Unknown'
                        }
        except Exception:
            pass
        
        return {'manufacturer': 'Unknown', 'model': 'Unknown'}
    
    def print_detailed_status(self):
        """詳細なNPU検出結果を表示"""
        print("=" * 80)
        print(" Enhanced NPU Detection Results")
        print("=" * 80)
        
        # システム情報
        print(f"System: {self.system_info.get('manufacturer', 'Unknown')} "
              f"{self.system_info.get('model', 'Unknown')}")
        print()
        
        # Intel AI Boost
        if self.detection_results['intel_ai_boost']:
            print("✓ Intel AI Boost NPU: DETECTED")
        else:
            print("✗ Intel AI Boost NPU: Not detected")
        
        # NPU Performance Counters
        npu_counters = self.detection_results['npu_counters']
        if npu_counters['available']:
            print("✓ NPU Performance Counters: AVAILABLE")
            for pattern_info in npu_counters['patterns_found']:
                print(f"    Pattern: {pattern_info['pattern']}")
                print(f"    Found: {pattern_info['count']} counters")
        else:
            print("✗ NPU Performance Counters: Not available")
        
        # タスクマネージャーNPU
        if self.detection_results['task_manager_npu']:
            print("✓ Task Manager NPU counters: Available")
        else:
            print("✗ Task Manager NPU counters: Not available")
        
        # DirectML
        directml = self.detection_results['directml_support']
        if directml['dll_exists']:
            print(f"✓ DirectML Support: Available ({directml['path']})")
        else:
            print("✗ DirectML Support: Not detected")
        
        # NPU関連デバイス
        if self.npu_devices:
            print(f"✓ NPU-related devices: {len(self.npu_devices)} found")
            for i, device in enumerate(self.npu_devices, 1):
                print(f"    {i}. {device['name']}")
                print(f"       Class: {device['class']}, Keyword: {device['keyword_matched']}")
                if device['description'] != device['name']:
                    print(f"       Description: {device['description']}")
        else:
            print("✗ NPU-related devices: None found")
        
        print()

class SmartNPUEstimator:
    """スマートNPU使用率推定クラス"""
    
    def __init__(self, window_size=120):  # 2分間のウィンドウ
        self.window_size = window_size
        self.cpu_history = deque(maxlen=window_size)
        self.ai_activity_history = deque(maxlen=window_size)
        self.process_cpu_history = defaultdict(lambda: deque(maxlen=window_size))
        
        # 学習用ベースライン
        self.baseline_cpu = deque(maxlen=300)  # 5分間のベースライン
        self.ai_peak_cpu = deque(maxlen=100)   # AI活動ピーク時
        
    def update_metrics(self, cpu_percent: float, ai_processes: List[Dict], ai_active: bool):
        """メトリクスを更新"""
        timestamp = time.time()
        
        # 基本履歴更新
        self.cpu_history.append((timestamp, cpu_percent))
        self.ai_activity_history.append((timestamp, ai_active))
        
        # プロセス別CPU履歴
        for proc in ai_processes:
            proc_key = f"{proc['name']}_{proc['type']}"
            self.process_cpu_history[proc_key].append((timestamp, proc['cpu_percent']))
        
        # ベースライン更新
        if ai_active:
            total_ai_cpu = sum(proc['cpu_percent'] for proc in ai_processes)
            self.ai_peak_cpu.append(total_ai_cpu)
        else:
            self.baseline_cpu.append(cpu_percent)
    
    def estimate_npu_usage(self) -> Optional[Dict[str, Any]]:
        """高度なNPU使用率推定"""
        if len(self.cpu_history) < 30:  # 最低30秒のデータが必要
            return None
        
        recent_data = list(self.cpu_history)[-30:]  # 最新30秒
        recent_ai_data = list(self.ai_activity_history)[-30:]
        
        # AI活動中とそうでない時のCPU使用率を分析
        ai_active_cpu = []
        ai_inactive_cpu = []
        
        for (t_cpu, cpu), (t_ai, ai_active) in zip(recent_data, recent_ai_data):
            if abs(t_cpu - t_ai) < 2:  # 時刻が近い場合
                if ai_active:
                    ai_active_cpu.append(cpu)
                else:
                    ai_inactive_cpu.append(cpu)
        
        if not ai_active_cpu or not ai_inactive_cpu:
            return self._simple_estimation()
        
        # 統計分析
        avg_ai_cpu = sum(ai_active_cpu) / len(ai_active_cpu)
        avg_inactive_cpu = sum(ai_inactive_cpu) / len(ai_inactive_cpu)
        
        # NPU効果の推定
        if avg_inactive_cpu > 0:
            cpu_efficiency = max(0, (avg_inactive_cpu - avg_ai_cpu) / avg_inactive_cpu)
        else:
            cpu_efficiency = 0
        
        # 信頼度計算
        confidence = min(100, len(ai_active_cpu) * 3)  # サンプル数ベース
        
        # NPU使用率推定
        if cpu_efficiency > 0.1:  # 10%以上の効率化
            npu_estimate = min(100, cpu_efficiency * 200)  # 効率化率の2倍を推定値
            npu_confidence = min(100, confidence + (cpu_efficiency * 100))
        else:
            npu_estimate = 0
            npu_confidence = confidence
        
        return {
            'npu_usage_estimate': npu_estimate,
            'confidence': npu_confidence,
            'cpu_efficiency': cpu_efficiency * 100,
            'ai_active_cpu_avg': avg_ai_cpu,
            'ai_inactive_cpu_avg': avg_inactive_cpu,
            'sample_count': len(ai_active_cpu),
            'method': 'advanced_analysis'
        }
    
    def _simple_estimation(self) -> Dict[str, Any]:
        """シンプルな推定（データ不足時）"""
        if not self.baseline_cpu or not self.ai_peak_cpu:
            return {
                'npu_usage_estimate': 0,
                'confidence': 0,
                'method': 'insufficient_data'
            }
        
        baseline_avg = sum(self.baseline_cpu) / len(self.baseline_cpu)
        ai_peak_avg = sum(self.ai_peak_cpu) / len(self.ai_peak_cpu)
        
        if baseline_avg > ai_peak_avg:
            efficiency = (baseline_avg - ai_peak_avg) / baseline_avg
            return {
                'npu_usage_estimate': min(100, efficiency * 150),
                'confidence': min(100, len(self.ai_peak_cpu) * 2),
                'method': 'simple_baseline'
            }
        
        return {
            'npu_usage_estimate': 0,
            'confidence': 50,
            'method': 'no_efficiency_detected'
        }

class EnhancedNPUMonitor:
    """拡張NPU監視クラス"""
    
    def __init__(self):
        self.detector = EnhancedNPUDetector()
        self.estimator = SmartNPUEstimator()
        
        # 既存のコレクター
        self.npu_collector = NPUPerformanceCollector() if HAS_PDH else None
        
        # 統計データ
        self.session_stats = {
            'start_time': time.time(),
            'npu_usage_samples': [],
            'ai_activity_samples': [],
            'cpu_samples': [],
            'process_detection_count': defaultdict(int)
        }
        
        # AI プロセス検出
        self.ai_patterns = {
            'frameworks': ['onnxruntime', 'pytorch', 'tensorflow', 'directml'],
            'applications': ['copilot', 'recall', 'studio_effects', 'windowsai'],
            'interpreters': ['python', 'node'],
            'ai_keywords': ['onnx', 'torch', 'tensorflow', 'ml', 'ai', 'neural', 'inference']
        }
    
    def detect_ai_processes(self) -> Tuple[List[Dict], bool]:
        """拡張AI プロセス検出"""
        ai_processes = []
        has_high_confidence_ai = False
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower()
                    
                    ai_type = None
                    confidence = 0
                    
                    # フレームワーク検出（高信頼度）
                    for framework in self.ai_patterns['frameworks']:
                        if framework in proc_name:
                            ai_type = f"Framework ({framework})"
                            confidence = 90
                            has_high_confidence_ai = True
                            break
                    
                    # アプリケーション検出（中信頼度）
                    if not ai_type:
                        for app in self.ai_patterns['applications']:
                            if app in proc_name:
                                ai_type = f"Application ({app})"
                                confidence = 70
                                break
                    
                    # インタープリター + コマンドライン解析（可変信頼度）
                    if not ai_type and any(interp in proc_name for interp in self.ai_patterns['interpreters']):
                        try:
                            cmdline = ' '.join(proc.cmdline()).lower()
                            for keyword in self.ai_patterns['ai_keywords']:
                                if keyword in cmdline:
                                    ai_type = f"Script ({keyword})"
                                    confidence = 60
                                    break
                        except (psutil.AccessDenied, psutil.NoSuchProcess):
                            pass
                    
                    if ai_type:
                        proc_data = {
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'type': ai_type,
                            'confidence': confidence,
                            'cpu_percent': proc_info['cpu_percent'] or 0,
                            'memory_percent': proc_info['memory_percent'] or 0
                        }
                        ai_processes.append(proc_data)
                        
                        # 統計更新
                        self.session_stats['process_detection_count'][ai_type] += 1
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        
        return ai_processes, has_high_confidence_ai
    
    def collect_comprehensive_metrics(self) -> Dict[str, Any]:
        """包括的メトリクス収集"""
        timestamp = time.time()
        
        # システムメトリクス
        cpu_percent = psutil.cpu_percent(interval=None)
        memory_percent = psutil.virtual_memory().percent
        cpu_per_core = psutil.cpu_percent(interval=None, percpu=True)
        
        # AI プロセス検出
        ai_processes, high_confidence_ai = self.detect_ai_processes()
        ai_active = len(ai_processes) > 0
        
        # NPU Performance Counter（利用可能な場合）
        npu_counter_data = {}
        if self.npu_collector and self.npu_collector.is_available():
            npu_counter_data = self.npu_collector.collect()
        
        # NPU使用率推定
        self.estimator.update_metrics(cpu_percent, ai_processes, ai_active)
        npu_estimation = self.estimator.estimate_npu_usage()
        
        # セッション統計更新
        self.session_stats['npu_usage_samples'].append((timestamp, npu_estimation))
        self.session_stats['ai_activity_samples'].append((timestamp, ai_active))
        self.session_stats['cpu_samples'].append((timestamp, cpu_percent))
        
        return {
            'timestamp': timestamp,
            'system': {
                'cpu_percent': cpu_percent,
                'memory_percent': memory_percent,
                'cpu_per_core': cpu_per_core
            },
            'ai_activity': {
                'processes': ai_processes,
                'active': ai_active,
                'high_confidence': high_confidence_ai,
                'total_count': len(ai_processes)
            },
            'npu': {
                'counter_data': npu_counter_data,
                'estimation': npu_estimation,
                'direct_available': bool(npu_counter_data)
            }
        }
    
    def display_comprehensive_metrics(self, metrics: Dict[str, Any]):
        """包括的メトリクス表示"""
        timestamp = datetime.fromtimestamp(metrics['timestamp'])
        
        print(f"\n[{timestamp.strftime('%H:%M:%S')}] " + "=" * 70)
        
        # NPU情報
        npu_info = metrics['npu']
        if npu_info['direct_available']:
            npu_values = list(npu_info['counter_data'].values())
            direct_usage = max(npu_values) if npu_values else 0
            print(f"NPU Direct  : {direct_usage:6.1f}% (Performance Counters)")
        else:
            print("NPU Direct  :    n/a (Performance Counters not available)")
        
        # NPU推定
        if npu_info['estimation']:
            est = npu_info['estimation']
            print(f"NPU Estimate: {est['npu_usage_estimate']:6.1f}% "
                  f"(Confidence: {est['confidence']:.0f}%, Method: {est['method']})")
            if 'cpu_efficiency' in est:
                print(f"              CPU Efficiency: {est['cpu_efficiency']:.1f}% improvement")
        else:
            print("NPU Estimate:    n/a (Insufficient data)")
        
        # AI活動
        ai_info = metrics['ai_activity']
        if ai_info['active']:
            confidence_indicator = "🔥" if ai_info['high_confidence'] else "💡"
            print(f"AI Activity : {confidence_indicator} {ai_info['total_count']} processes active")
            
            # 高信頼度プロセスを優先表示
            sorted_processes = sorted(ai_info['processes'], 
                                    key=lambda x: x['confidence'], reverse=True)
            
            for proc in sorted_processes[:3]:  # トップ3を表示
                print(f"              {proc['name']} (PID:{proc['pid']}) - "
                      f"CPU:{proc['cpu_percent']:.1f}%, "
                      f"Type:{proc['type']}, "
                      f"Conf:{proc['confidence']}%")
        else:
            print("AI Activity :    No AI processes detected")
        
        # システムリソース
        sys_info = metrics['system']
        core_usage = f"[{', '.join(f'{c:.0f}' for c in sys_info['cpu_per_core'][:4])}...]" \
                     if len(sys_info['cpu_per_core']) > 4 else \
                     f"[{', '.join(f'{c:.0f}' for c in sys_info['cpu_per_core'])}]"
        
        print(f"System      : CPU {sys_info['cpu_percent']:5.1f}% {core_usage}, "
              f"Memory {sys_info['memory_percent']:5.1f}%")
    
    def print_session_summary(self):
        """セッション統計表示"""
        session_duration = time.time() - self.session_stats['start_time']
        
        print("\n" + "=" * 80)
        print(" Session Summary")
        print("=" * 80)
        print(f"Duration: {session_duration:.0f} seconds ({session_duration/60:.1f} minutes)")
        
        # AI活動統計
        ai_samples = self.session_stats['ai_activity_samples']
        ai_active_count = sum(1 for _, active in ai_samples if active)
        ai_active_ratio = (ai_active_count / len(ai_samples) * 100) if ai_samples else 0
        
        print(f"AI Activity: {ai_active_ratio:.1f}% of time ({ai_active_count}/{len(ai_samples)} samples)")
        
        # プロセス検出統計
        print("Process Detection Summary:")
        for proc_type, count in self.session_stats['process_detection_count'].items():
            print(f"  {proc_type}: {count} detections")
        
        # CPU統計
        cpu_samples = [cpu for _, cpu in self.session_stats['cpu_samples']]
        if cpu_samples:
            print(f"CPU Usage: Avg {sum(cpu_samples)/len(cpu_samples):.1f}%, "
                  f"Max {max(cpu_samples):.1f}%, Min {min(cpu_samples):.1f}%")
    
    def start_monitoring(self):
        """監視開始"""
        # 詳細検出結果表示
        self.detector.print_detailed_status()
        
        print("Starting Enhanced NPU Monitoring...")
        print("Features: NPU Detection, AI Process Analysis, Smart Usage Estimation")
        print("Press Ctrl+C to stop\n")
        
        # CPU priming
        psutil.cpu_percent(interval=None)
        
        try:
            while True:
                metrics = self.collect_comprehensive_metrics()
                self.display_comprehensive_metrics(metrics)
                time.sleep(REFRESH_SEC)
                
        except KeyboardInterrupt:
            print("\n\nEnhanced NPU Monitoring stopped.")
            self.print_session_summary()

# NPUPerformanceCollector クラス（既存のものを再利用）
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
                    instance = path[path.find('(')+1:path.find(')')] if '(' in path and ')' in path else path
                    
                    numeric_val = float(val)
                    if not math.isnan(numeric_val) and numeric_val >= 0:
                        data[instance] = numeric_val
                except Exception:
                    pass
            
            return data
        except Exception:
            return {}

def main():
    """メイン関数"""
    print("Enhanced NPU Monitor v2.0")
    print("Advanced NPU and AI inference activity monitoring")
    print("Features: Device detection, Process analysis, Smart estimation")
    print()
    
    monitor = EnhancedNPUMonitor()
    monitor.start_monitoring()

if __name__ == "__main__":
    main()