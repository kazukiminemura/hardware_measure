#!/usr/bin/env python3
"""
最終統合NPU監視ソリューション
ETW + PDH + 間接監視のハイブリッドアプローチ
"""

import subprocess
import time
import os
import json
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable, Tuple
from dataclasses import dataclass, asdict
from collections import deque

try:
    import win32pdh
    import wmi
    import psutil
    HAS_ALL_DEPS = True
except ImportError as e:
    print(f"Missing dependencies: {e}")
    HAS_ALL_DEPS = False

@dataclass
class NPUMonitoringData:
    """NPU監視データ"""
    timestamp: str
    npu_utilization_etw: Optional[float]  # ETW直接監視
    npu_utilization_estimated: float     # 間接推定
    confidence_level: str
    monitoring_methods: List[str]
    etw_events_captured: int
    ai_processes: List[Dict]
    gpu_compute_usage: float
    intel_npu_device_status: str
    power_consumption_change: bool

class UltimateNPUMonitor:
    """最終統合NPU監視システム"""
    
    def __init__(self):
        self.monitoring_active = False
        self.results_history = deque(maxlen=100)
        
        # ETW関連
        self.etw_providers = {
            "Intel-NPU-D3D12": "{11A83531-4AC9-4142-8D35-E474B6B3C597}",
            "Intel-NPU-Kmd": "{B3B1AAB1-3C04-4B6D-A069-59547BC18233}",
            "Intel-NPU-LevelZero": "{416F823F-2CE2-44B9-A1BA-7E98BA4CD4BA}"
        }
        self.etw_sessions = []
        self.etw_available = False
        
        # PDH関連
        self.pdh_counters = {
            'gpu_compute': [],
            'power_meter': [],
            'processor_info': []
        }
        
        # デバイス情報
        self.npu_device_info = {}
        
        print("Initializing Ultimate NPU Monitor...")
        self._initialize_monitoring_capabilities()
    
    def _initialize_monitoring_capabilities(self):
        """監視能力の初期化"""
        # 1. NPUデバイス検出
        self._detect_npu_device()
        
        # 2. ETW利用可能性確認
        self._check_etw_availability()
        
        # 3. PDHカウンター発見
        self._discover_pdh_counters()
    
    def _detect_npu_device(self) -> bool:
        """NPUデバイス検出"""
        try:
            c = wmi.WMI()
            for device in c.Win32_PnPEntity():
                if device.Name and 'Intel(R) AI Boost' in device.Name:
                    self.npu_device_info = {
                        'name': device.Name,
                        'status': device.Status,
                        'device_id': device.DeviceID,
                        'manufacturer': device.Manufacturer
                    }
                    print(f"✓ NPU Device: {device.Name} ({device.Status})")
                    return True
            return False
        except:
            return False
    
    def _check_etw_availability(self) -> bool:
        """ETW監視の利用可能性確認"""
        try:
            # 管理者権限確認
            result = subprocess.run(
                ["reg", "query", "HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\Policies\\System", "/v", "EnableLUA"],
                capture_output=True, text=True, timeout=5
            )
            
            is_admin = result.returncode == 0
            
            if is_admin:
                # ETWプロバイダーテスト
                test_provider = list(self.etw_providers.values())[0]
                test_cmd = ["logman", "start", "NPU_Test", "-p", test_provider, "-o", "test.etl", "-ets"]
                
                test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=5)
                if test_result.returncode == 0:
                    # すぐに停止
                    subprocess.run(["logman", "stop", "NPU_Test", "-ets"], capture_output=True, timeout=5)
                    if os.path.exists("test.etl"):
                        os.remove("test.etl")
                    
                    self.etw_available = True
                    print("✓ ETW NPU monitoring available (Administrator)")
                    return True
                else:
                    print("⚠ ETW providers exist but may not be active")
            else:
                print("⚠ ETW monitoring requires Administrator privileges")
            
        except Exception as e:
            print(f"✗ ETW monitoring not available: {e}")
        
        return False
    
    def _discover_pdh_counters(self):
        """PDHカウンター発見"""
        if not HAS_ALL_DEPS:
            return
        
        try:
            # GPU Compute engines
            gpu_paths = win32pdh.ExpandCounterPath(r"\GPU Engine(*engtype_Compute)\Utilization Percentage")
            self.pdh_counters['gpu_compute'] = gpu_paths[:5]  # 最初の5個
            
            # Power meters
            power_paths = win32pdh.ExpandCounterPath(r"\Power Meter(*)\Power")
            self.pdh_counters['power_meter'] = power_paths
            
            # Processor utility
            proc_paths = win32pdh.ExpandCounterPath(r"\Processor Information(_Total)\% Processor Utility")
            self.pdh_counters['processor_info'] = proc_paths
            
            print(f"✓ PDH counters: GPU({len(self.pdh_counters['gpu_compute'])}), Power({len(self.pdh_counters['power_meter'])})")
            
        except Exception as e:
            print(f"✗ PDH counter discovery failed: {e}")
    
    def start_etw_monitoring(self) -> bool:
        """ETW監視開始"""
        if not self.etw_available:
            return False
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        for provider_name, provider_guid in self.etw_providers.items():
            session_name = f"NPU_{provider_name.replace('-', '_')}_{timestamp}"
            trace_file = f"npu_{provider_name.lower().replace('-', '_')}_{timestamp}.etl"
            
            try:
                start_cmd = [
                    "logman", "start", session_name,
                    "-p", provider_guid,
                    "-o", trace_file,
                    "-ets"
                ]
                
                result = subprocess.run(start_cmd, capture_output=True, text=True)
                if result.returncode == 0:
                    self.etw_sessions.append((session_name, trace_file))
                    print(f"✓ Started ETW: {provider_name}")
                
            except Exception as e:
                print(f"✗ Failed to start ETW {provider_name}: {e}")
        
        return len(self.etw_sessions) > 0
    
    def stop_etw_monitoring(self) -> int:
        """ETW監視停止"""
        events_captured = 0
        
        for session_name, trace_file in self.etw_sessions:
            try:
                result = subprocess.run(
                    ["logman", "stop", session_name, "-ets"],
                    capture_output=True, text=True
                )
                
                if result.returncode == 0 and os.path.exists(trace_file):
                    file_size = os.path.getsize(trace_file)
                    if file_size > 1024:  # 1KB以上なら有効
                        events_captured += 1
                        print(f"✓ ETW trace: {trace_file} ({file_size} bytes)")
                
            except Exception as e:
                print(f"✗ Error stopping ETW session: {e}")
        
        self.etw_sessions.clear()
        return events_captured
    
    def sample_pdh_metrics(self) -> Dict[str, float]:
        """PDHメトリクスサンプリング"""
        metrics = {
            'gpu_compute_avg': 0.0,
            'power_current': 0.0,
            'cpu_utility': 0.0
        }
        
        if not HAS_ALL_DEPS:
            return metrics
        
        try:
            query = win32pdh.OpenQuery()
            counters = {}
            
            # GPU Compute
            if self.pdh_counters['gpu_compute']:
                gpu_counter = win32pdh.AddCounter(query, self.pdh_counters['gpu_compute'][0])
                counters['gpu'] = gpu_counter
            
            # Power
            if self.pdh_counters['power_meter']:
                power_counter = win32pdh.AddCounter(query, self.pdh_counters['power_meter'][0])
                counters['power'] = power_counter
            
            # CPU
            if self.pdh_counters['processor_info']:
                cpu_counter = win32pdh.AddCounter(query, self.pdh_counters['processor_info'][0])
                counters['cpu'] = cpu_counter
            
            # サンプリング
            win32pdh.CollectQueryData(query)
            time.sleep(0.5)
            win32pdh.CollectQueryData(query)
            
            # 値取得
            for counter_type, counter in counters.items():
                try:
                    _, value = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
                    if counter_type == 'gpu':
                        metrics['gpu_compute_avg'] = value
                    elif counter_type == 'power':
                        metrics['power_current'] = value
                    elif counter_type == 'cpu':
                        metrics['cpu_utility'] = value
                except:
                    pass
            
            win32pdh.CloseQuery(query)
            
        except Exception as e:
            print(f"PDH sampling error: {e}")
        
        return metrics
    
    def detect_ai_processes(self) -> List[Dict]:
        """AI関連プロセス検出"""
        ai_processes = []
        
        ai_patterns = [
            'python.exe', 'pytorch', 'tensorflow', 'onnx', 'winml',
            'directml', 'openvino', 'inference', 'model'
        ]
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower() if proc_info['name'] else ''
                    
                    if any(pattern in proc_name for pattern in ai_patterns):
                        if proc_info['cpu_percent'] and proc_info['cpu_percent'] > 1.0:
                            ai_processes.append({
                                'pid': proc_info['pid'],
                                'name': proc_info['name'],
                                'cpu_percent': proc_info['cpu_percent'],
                                'memory_percent': proc_info['memory_percent']
                            })
                            
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            print(f"AI process detection error: {e}")
        
        return ai_processes
    
    def estimate_npu_utilization(self, pdh_metrics: Dict[str, float], ai_processes: List[Dict], etw_events: int) -> Tuple[float, str]:
        """NPU使用率推定"""
        utilization = 0.0
        confidence = 'low'
        
        # ETW イベントベース推定
        if etw_events > 0:
            etw_factor = min(etw_events * 10.0, 50.0)  # ETWイベント数ベース
            utilization += etw_factor
            confidence = 'high'
        
        # AI プロセスベース推定
        if ai_processes:
            ai_cpu_total = sum(proc['cpu_percent'] for proc in ai_processes)
            ai_factor = min(ai_cpu_total * 0.3, 30.0)
            utilization += ai_factor
            
            if ai_cpu_total > 20.0:
                confidence = 'medium-high' if confidence == 'low' else confidence
        
        # GPU Computeベース推定
        gpu_usage = pdh_metrics.get('gpu_compute_avg', 0.0)
        if gpu_usage > 5.0:
            gpu_factor = min(gpu_usage * 0.5, 20.0)
            utilization += gpu_factor
            confidence = 'medium' if confidence == 'low' else confidence
        
        # CPU効率パターン
        cpu_util = pdh_metrics.get('cpu_utility', 0.0)
        if cpu_util < 30.0 and ai_processes:  # 低CPU使用率でAI活動 = NPUオフロード
            efficiency_bonus = (30.0 - cpu_util) * 0.5
            utilization += efficiency_bonus
        
        return min(utilization, 100.0), confidence
    
    def comprehensive_npu_monitoring_cycle(self) -> NPUMonitoringData:
        """包括的NPU監視サイクル"""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # ETW監視（短時間）
        etw_events = 0
        if self.etw_available:
            if self.start_etw_monitoring():
                time.sleep(2)  # 2秒間監視
                etw_events = self.stop_etw_monitoring()
        
        # PDHメトリクス取得
        pdh_metrics = self.sample_pdh_metrics()
        
        # AI プロセス検出
        ai_processes = self.detect_ai_processes()
        
        # NPU使用率推定
        npu_utilization, confidence = self.estimate_npu_utilization(pdh_metrics, ai_processes, etw_events)
        
        # 監視方法リスト
        monitoring_methods = []
        if etw_events > 0:
            monitoring_methods.append('ETW_Direct')
        if pdh_metrics['gpu_compute_avg'] > 0:
            monitoring_methods.append('PDH_GPU_Compute')
        if ai_processes:
            monitoring_methods.append('Process_Detection')
        if pdh_metrics['power_current'] > 0:
            monitoring_methods.append('Power_Monitoring')
        
        return NPUMonitoringData(
            timestamp=timestamp,
            npu_utilization_etw=etw_events * 10.0 if etw_events > 0 else None,
            npu_utilization_estimated=npu_utilization,
            confidence_level=confidence,
            monitoring_methods=monitoring_methods,
            etw_events_captured=etw_events,
            ai_processes=ai_processes,
            gpu_compute_usage=pdh_metrics['gpu_compute_avg'],
            intel_npu_device_status=self.npu_device_info.get('status', 'Unknown'),
            power_consumption_change=pdh_metrics['power_current'] > 0
        )
    
    def start_continuous_monitoring(self, interval: float = 10.0, duration: int = 60):
        """連続監視開始"""
        print(f"🚀 Starting Ultimate NPU Monitoring")
        print(f"   Interval: {interval}s, Duration: {duration}s")
        print(f"   NPU Device: {self.npu_device_info.get('name', 'Not detected')}")
        print(f"   ETW Available: {'✅' if self.etw_available else '❌'}")
        print(f"   PDH Counters: {len(self.pdh_counters['gpu_compute']) + len(self.pdh_counters['power_meter'])}")
        print()
        
        self.monitoring_active = True
        start_time = time.time()
        
        try:
            while self.monitoring_active and (time.time() - start_time) < duration:
                # 監視サイクル実行
                data = self.comprehensive_npu_monitoring_cycle()
                self.results_history.append(data)
                
                # 結果表示
                print(f"[{data.timestamp}]")
                print(f"  NPU Utilization: {data.npu_utilization_estimated:.1f}% ({data.confidence_level})")
                print(f"  Methods: {', '.join(data.monitoring_methods)}")
                print(f"  ETW Events: {data.etw_events_captured}")
                print(f"  AI Processes: {len(data.ai_processes)}")
                print(f"  GPU Compute: {data.gpu_compute_usage:.1f}%")
                print()
                
                time.sleep(interval)
                
        except KeyboardInterrupt:
            print("Monitoring interrupted by user")
        finally:
            self.monitoring_active = False
    
    def get_monitoring_summary(self) -> Dict:
        """監視サマリー取得"""
        if not self.results_history:
            return {'status': 'no_data'}
        
        recent_data = list(self.results_history)
        
        # 統計計算
        avg_utilization = sum(d.npu_utilization_estimated for d in recent_data) / len(recent_data)
        max_utilization = max(d.npu_utilization_estimated for d in recent_data)
        total_etw_events = sum(d.etw_events_captured for d in recent_data)
        
        # 使用された監視方法
        all_methods = set()
        for d in recent_data:
            all_methods.update(d.monitoring_methods)
        
        # 信頼度分布
        confidence_counts = {}
        for d in recent_data:
            confidence_counts[d.confidence_level] = confidence_counts.get(d.confidence_level, 0) + 1
        
        return {
            'total_samples': len(recent_data),
            'avg_npu_utilization': avg_utilization,
            'max_npu_utilization': max_utilization,
            'total_etw_events': total_etw_events,
            'monitoring_methods_used': list(all_methods),
            'confidence_distribution': confidence_counts,
            'npu_device_status': self.npu_device_info.get('status', 'Unknown'),
            'etw_monitoring_available': self.etw_available
        }

def main():
    """メイン関数"""
    print("=" * 80)
    print(" ULTIMATE NPU MONITORING SOLUTION")
    print(" ETW + PDH + Indirect Monitoring Hybrid Approach")
    print("=" * 80)
    
    if not HAS_ALL_DEPS:
        print("❌ Missing dependencies. Please install: pip install pywin32 wmi psutil")
        return
    
    monitor = UltimateNPUMonitor()
    
    print(f"\\n📋 System Capabilities:")
    print(f"  NPU Device: {monitor.npu_device_info.get('name', '❌ Not detected')}")
    print(f"  ETW Monitoring: {'✅ Available' if monitor.etw_available else '⚠ Requires Admin'}")
    print(f"  PDH Counters: {len(monitor.pdh_counters['gpu_compute']) + len(monitor.pdh_counters['power_meter'])} available")
    
    try:
        # 30秒間の監視デモ
        monitor.start_continuous_monitoring(interval=5.0, duration=30)
        
        # 最終サマリー
        print(f"\\n{'='*60}")
        print(" MONITORING SUMMARY")
        print(f"{'='*60}")
        
        summary = monitor.get_monitoring_summary()
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        
    except Exception as e:
        print(f"❌ Error during monitoring: {e}")

if __name__ == "__main__":
    main()