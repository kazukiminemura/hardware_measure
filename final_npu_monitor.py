#!/usr/bin/env python3
"""
最終NPU監視戦略スクリプト
win32pdh調査結果に基づく実用的なNPU監視ソリューション
"""

import time
import json
import threading
from datetime import datetime, timezone
from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
from collections import deque, defaultdict

try:
    import win32pdh
    import wmi
    import psutil
    HAS_DEPS = True
except ImportError as e:
    print(f"Missing dependencies: {e}")
    HAS_DEPS = False

@dataclass
class NPUMonitoringResult:
    """NPU監視結果データクラス"""
    timestamp: str
    npu_estimated_usage: float
    confidence_level: str
    monitoring_method: str
    ai_processes: List[Dict]
    gpu_compute_usage: float
    cpu_efficiency_pattern: float
    power_consumption: Optional[float]
    detection_signals: List[str]

class FinalNPUMonitor:
    """最終NPU監視システム"""
    
    def __init__(self):
        self.monitoring_active = False
        self.results_history = deque(maxlen=100)
        self.ai_process_patterns = [
            'python.exe', 'pytorch', 'tensorflow', 'onnx', 'winml',
            'ai', 'ml', 'neural', 'inference', 'model'
        ]
        
        # PDH調査結果に基づく利用可能カウンター
        self.available_counters = {
            'power_meter': [],
            'gpu_compute': [],
            'processor_info': [],
            'thermal': []
        }
        
        self.callback_functions = []
        
        print("Initializing Final NPU Monitor based on PDH investigation results...")
        self._discover_available_counters()
    
    def _discover_available_counters(self):
        """PDH調査で判明した利用可能カウンターを発見"""
        if not HAS_DEPS:
            print("Dependencies not available for counter discovery")
            return
        
        try:
            # Power Meter カウンター（NPU活動の間接指標）
            try:
                power_paths = win32pdh.ExpandCounterPath(r"\Power Meter(*)\Power")
                self.available_counters['power_meter'] = power_paths
                if power_paths:
                    print(f"✓ Power monitoring available: {len(power_paths)} meters")
            except:
                print("✗ Power meters not available")
            
            # GPU Compute engines（NPU候補）
            try:
                compute_paths = win32pdh.ExpandCounterPath(r"\GPU Engine(*engtype_Compute)\Utilization Percentage")
                self.available_counters['gpu_compute'] = compute_paths
                if compute_paths:
                    print(f"✓ GPU Compute monitoring available: {len(compute_paths)} engines")
            except:
                print("✗ GPU Compute engines not available")
            
            # Processor Information（CPU効率パターン）
            try:
                proc_paths = win32pdh.ExpandCounterPath(r"\Processor Information(*)\% Processor Utility")
                self.available_counters['processor_info'] = proc_paths
                if proc_paths:
                    print(f"✓ Processor utility monitoring available: {len(proc_paths)} processors")
            except:
                print("✗ Processor Information not available")
                
        except Exception as e:
            print(f"Error discovering counters: {e}")
    
    def detect_intel_ai_boost(self) -> bool:
        """Intel AI Boost NPU検出"""
        try:
            c = wmi.WMI()
            for pnp_device in c.Win32_PnPEntity():
                if pnp_device.Name and 'Intel(R) AI Boost' in pnp_device.Name:
                    print(f"✓ Intel AI Boost NPU detected: {pnp_device.Name}")
                    return True
            return False
        except:
            return False
    
    def monitor_ai_processes(self) -> List[Dict]:
        """AI関連プロセス監視"""
        ai_processes = []
        
        try:
            for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent', 'cmdline']):
                try:
                    proc_info = proc.info
                    proc_name = proc_info['name'].lower() if proc_info['name'] else ''
                    cmdline = ' '.join(proc_info['cmdline']) if proc_info['cmdline'] else ''
                    cmdline_lower = cmdline.lower()
                    
                    # AI関連プロセスの検出
                    is_ai_process = any(
                        pattern in proc_name or pattern in cmdline_lower 
                        for pattern in self.ai_process_patterns
                    )
                    
                    if is_ai_process and proc_info['cpu_percent'] and proc_info['cpu_percent'] > 1.0:
                        ai_processes.append({
                            'pid': proc_info['pid'],
                            'name': proc_info['name'],
                            'cpu_percent': proc_info['cpu_percent'],
                            'memory_percent': proc_info['memory_percent'],
                            'ai_confidence': self._calculate_ai_confidence(proc_name, cmdline_lower)
                        })
                        
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
        except Exception as e:
            print(f"Error monitoring AI processes: {e}")
        
        return sorted(ai_processes, key=lambda x: x['ai_confidence'], reverse=True)
    
    def _calculate_ai_confidence(self, proc_name: str, cmdline: str) -> float:
        """AI関連プロセスの信頼度計算"""
        confidence = 0.0
        
        # 直接的なAI指標
        if any(kw in proc_name for kw in ['ai', 'ml', 'neural', 'onnx']):
            confidence += 0.8
        if any(kw in cmdline for kw in ['tensorflow', 'pytorch', 'winml', 'directml']):
            confidence += 0.7
        if any(kw in cmdline for kw in ['model', 'inference', 'predict']):
            confidence += 0.5
        
        # Python関連（AI開発でよく使用）
        if 'python' in proc_name and any(kw in cmdline for kw in ['numpy', 'torch', 'tf']):
            confidence += 0.6
        
        return min(confidence, 1.0)
    
    def estimate_npu_usage_indirect(self) -> Dict[str, any]:
        """間接的NPU使用率推定"""
        estimation_data = {
            'npu_usage_estimate': 0.0,
            'confidence': 'low',
            'method': 'indirect',
            'indicators': []
        }
        
        try:
            # AI プロセス検出
            ai_processes = self.monitor_ai_processes()
            if ai_processes:
                ai_cpu_total = sum(proc['cpu_percent'] for proc in ai_processes)
                ai_confidence_avg = sum(proc['ai_confidence'] for proc in ai_processes) / len(ai_processes)
                
                # AI活動ベースのNPU推定
                if ai_confidence_avg > 0.7 and ai_cpu_total > 10.0:
                    estimation_data['npu_usage_estimate'] = min(ai_cpu_total * 0.3, 100.0)
                    estimation_data['confidence'] = 'medium'
                    estimation_data['indicators'].append(f'High-confidence AI processes (CPU: {ai_cpu_total:.1f}%)')
                elif ai_confidence_avg > 0.5:
                    estimation_data['npu_usage_estimate'] = min(ai_cpu_total * 0.2, 50.0)
                    estimation_data['confidence'] = 'low-medium'
                    estimation_data['indicators'].append(f'Medium-confidence AI processes')
                
                estimation_data['ai_processes'] = ai_processes
            
            # CPU効率パターン分析
            cpu_percent = psutil.cpu_percent(interval=0.1)
            cpu_count = psutil.cpu_count()
            
            # 低CPU使用率での高効率作業の検出（NPUオフロードの可能性）
            if cpu_percent < 20.0 and len(ai_processes) > 0:
                efficiency_bonus = (20.0 - cpu_percent) * 2.0
                estimation_data['npu_usage_estimate'] += efficiency_bonus
                estimation_data['indicators'].append(f'High efficiency pattern (low CPU with AI activity)')
            
            # GPU Compute engine監視（利用可能な場合）
            gpu_activity = self._sample_gpu_compute_activity()
            if gpu_activity > 5.0:
                estimation_data['npu_usage_estimate'] += gpu_activity * 0.5
                estimation_data['indicators'].append(f'GPU Compute activity: {gpu_activity:.1f}%')
                estimation_data['confidence'] = 'medium-high'
            
            # 電力消費変化（利用可能な場合）
            power_change = self._detect_power_pattern_change()
            if power_change:
                estimation_data['indicators'].append(f'Power consumption pattern change detected')
                estimation_data['npu_usage_estimate'] += 10.0
            
            # 最終調整
            estimation_data['npu_usage_estimate'] = min(estimation_data['npu_usage_estimate'], 100.0)
            
            # 信頼度の再評価
            if len(estimation_data['indicators']) >= 3:
                estimation_data['confidence'] = 'high'
            elif len(estimation_data['indicators']) >= 2:
                estimation_data['confidence'] = 'medium'
                
        except Exception as e:
            print(f"Error in NPU estimation: {e}")
            estimation_data['indicators'].append(f'Estimation error: {e}')
        
        return estimation_data
    
    def _sample_gpu_compute_activity(self) -> float:
        """GPU Compute活動のサンプリング"""
        if not self.available_counters['gpu_compute']:
            return 0.0
        
        try:
            # 最初のCompute engineをサンプル
            compute_path = self.available_counters['gpu_compute'][0]
            
            query = win32pdh.OpenQuery()
            counter = win32pdh.AddCounter(query, compute_path)
            
            win32pdh.CollectQueryData(query)
            time.sleep(0.1)
            win32pdh.CollectQueryData(query)
            
            _, value = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
            win32pdh.CloseQuery(query)
            
            return value
            
        except:
            return 0.0
    
    def _detect_power_pattern_change(self) -> bool:
        """電力パターン変化の検出"""
        if not self.available_counters['power_meter']:
            return False
        
        try:
            # 簡単な電力変化検出（実装の場合はより詳細な分析が必要）
            power_path = self.available_counters['power_meter'][0]
            
            query = win32pdh.OpenQuery()
            counter = win32pdh.AddCounter(query, power_path)
            
            win32pdh.CollectQueryData(query)
            time.sleep(0.5)
            win32pdh.CollectQueryData(query)
            
            _, current_power = win32pdh.GetFormattedCounterValue(counter, win32pdh.PDH_FMT_DOUBLE)
            win32pdh.CloseQuery(query)
            
            # ベースライン比較（簡易版）
            if hasattr(self, '_baseline_power'):
                change_percent = abs(current_power - self._baseline_power) / self._baseline_power
                return change_percent > 0.05  # 5%以上の変化
            else:
                self._baseline_power = current_power
                return False
                
        except:
            return False
    
    def start_monitoring(self, interval: float = 5.0, callback: Optional[Callable] = None):
        """NPU監視開始"""
        if self.monitoring_active:
            print("Monitoring is already active")
            return
        
        self.monitoring_active = True
        
        if callback:
            self.callback_functions.append(callback)
        
        def monitoring_loop():
            print(f"Starting NPU monitoring (interval: {interval}s)")
            
            while self.monitoring_active:
                try:
                    # NPU使用率推定
                    estimation_data = self.estimate_npu_usage_indirect()
                    
                    # AI プロセス監視
                    ai_processes = estimation_data.get('ai_processes', [])
                    
                    # GPU Compute サンプリング
                    gpu_compute_usage = self._sample_gpu_compute_activity()
                    
                    # 結果作成
                    result = NPUMonitoringResult(
                        timestamp=datetime.now(timezone.utc).isoformat(),
                        npu_estimated_usage=estimation_data['npu_usage_estimate'],
                        confidence_level=estimation_data['confidence'],
                        monitoring_method=estimation_data['method'],
                        ai_processes=ai_processes,
                        gpu_compute_usage=gpu_compute_usage,
                        cpu_efficiency_pattern=psutil.cpu_percent(interval=0.1),
                        power_consumption=None,  # 実装されていない場合
                        detection_signals=estimation_data['indicators']
                    )
                    
                    # 結果保存
                    self.results_history.append(result)
                    
                    # コールバック呼び出し
                    for callback_func in self.callback_functions:
                        try:
                            callback_func(result)
                        except Exception as e:
                            print(f"Callback error: {e}")
                    
                    time.sleep(interval)
                    
                except Exception as e:
                    print(f"Monitoring error: {e}")
                    time.sleep(interval)
        
        # 監視スレッド開始
        self.monitoring_thread = threading.Thread(target=monitoring_loop, daemon=True)
        self.monitoring_thread.start()
    
    def stop_monitoring(self):
        """NPU監視停止"""
        self.monitoring_active = False
        print("NPU monitoring stopped")
    
    def get_current_status(self) -> Dict:
        """現在のNPUステータス取得"""
        if not self.results_history:
            return {"status": "no_data"}
        
        latest_result = self.results_history[-1]
        return {
            "timestamp": latest_result.timestamp,
            "npu_estimated_usage": latest_result.npu_estimated_usage,
            "confidence": latest_result.confidence_level,
            "ai_processes_count": len(latest_result.ai_processes),
            "detection_signals": latest_result.detection_signals,
            "monitoring_method": latest_result.monitoring_method
        }
    
    def get_monitoring_summary(self) -> Dict:
        """監視サマリー取得"""
        if not self.results_history:
            return {"summary": "no_data"}
        
        recent_results = list(self.results_history)[-10:]  # 最新10件
        
        avg_usage = sum(r.npu_estimated_usage for r in recent_results) / len(recent_results)
        max_usage = max(r.npu_estimated_usage for r in recent_results)
        
        # 信頼度分布
        confidence_counts = defaultdict(int)
        for r in recent_results:
            confidence_counts[r.confidence_level] += 1
        
        return {
            "sample_count": len(recent_results),
            "avg_npu_usage": avg_usage,
            "max_npu_usage": max_usage,
            "confidence_distribution": dict(confidence_counts),
            "available_counters": {
                k: len(v) for k, v in self.available_counters.items()
            }
        }

def demo_callback(result: NPUMonitoringResult):
    """デモ用コールバック関数"""
    print(f"\n[NPU Monitor] {result.timestamp}")
    print(f"  NPU Usage Estimate: {result.npu_estimated_usage:.1f}% ({result.confidence_level})")
    print(f"  AI Processes: {len(result.ai_processes)}")
    print(f"  GPU Compute: {result.gpu_compute_usage:.1f}%")
    print(f"  Detection Signals: {len(result.detection_signals)}")
    for signal in result.detection_signals:
        print(f"    - {signal}")

def main():
    """メイン関数"""
    print("=" * 80)
    print(" FINAL NPU MONITORING SOLUTION")
    print(" Based on win32pdh Investigation Results")
    print("=" * 80)
    
    if not HAS_DEPS:
        print("ERROR: Required dependencies not available")
        print("Please install: pip install pywin32 wmi psutil")
        return
    
    # NPU監視システム初期化
    monitor = FinalNPUMonitor()
    
    # Intel AI Boost検出
    if monitor.detect_intel_ai_boost():
        print("✓ Intel AI Boost NPU hardware detected")
    else:
        print("ℹ Intel AI Boost NPU not detected (may still be present)")
    
    print(f"\nAvailable monitoring capabilities:")
    summary = monitor.get_monitoring_summary()
    if 'available_counters' in summary:
        for counter_type, count in summary['available_counters'].items():
            status = "✓" if count > 0 else "✗"
            print(f"  {status} {counter_type}: {count} counters")
    
    print(f"\nStarting demonstration monitoring...")
    print(f"Note: This uses indirect methods since direct NPU counters are not available")
    print(f"Press Ctrl+C to stop monitoring")
    
    try:
        # 監視開始（デモ用コールバック付き）
        monitor.start_monitoring(interval=3.0, callback=demo_callback)
        
        # 30秒間監視
        time.sleep(30)
        
        # 監視停止
        monitor.stop_monitoring()
        
        # 最終サマリー
        print(f"\n{'='*60}")
        print(" MONITORING SUMMARY")
        print(f"{'='*60}")
        
        final_summary = monitor.get_monitoring_summary()
        print(json.dumps(final_summary, indent=2, ensure_ascii=False))
        
    except KeyboardInterrupt:
        print(f"\nMonitoring interrupted by user")
        monitor.stop_monitoring()
    
    except Exception as e:
        print(f"Error during monitoring: {e}")
        monitor.stop_monitoring()

if __name__ == "__main__":
    main()